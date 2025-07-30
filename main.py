import os
import subprocess
import fitz  # PyMuPDF
import json
import re
from PIL import Image
import io
import tempfile
import easyocr
import numpy as np
import cv2
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, MatchAny
from sklearn.metrics.pairwise import cosine_similarity
import uuid

# === STEP 1: CHUNKING ===

def debug_print_chunking(text_added, image_added):
    """
    Print a debug summary of the text and image chunks added.
    """
    summary = []
    if text_added:
        summary.append("✅ text")
    if image_added:
        summary.append(f"✅ image")
    if not text_added and not image_added:
        summary.append("⚪ skipped")
    print(f"({', '.join(summary)})")

def add_text_chunk(text_content, page_num, all_metadata, output_dir, pdf_path):
    """
    Add a text chunk to the metadata.
    Args:
        text_content (str): The text content to add
        page_num (int): The page number of the chunk
        all_metadata (dict): The metadata dictionary
        output_dir (str): The output directory
        pdf_path (str): The path to the PDF file

    Returns:
        bool: True if the text chunk was added successfully, False otherwise
    """
    print("Converting text chunk")
    try:
        if text_content.strip():
            all_metadata[pdf_path]["chunks"].append({
                "type": "text",
                "page": page_num + 1,
                "content": text_content.strip()
            })
    except Exception as e:
        print(f"Error converting text chunk: {e}")
        return False
    return True

def add_image_chunk(page, page_num, all_metadata, output_dir, pdf_path):
    """
    Add an image chunk to the metadata.
    Args:
        page (fitz.Page): The page to extract the image from
        page_num (int): The page number of the chunk
        all_metadata (dict): The metadata dictionary
        output_dir (str): The output directory
        pdf_path (str): The path to the PDF file

    Returns:
        bool: True if the image chunk was added successfully, False otherwise
    """
    print("Converting image chunk")
    try:
        pix = page.get_pixmap()
        img_data = pix.tobytes("png")
        image_filename = f'{pdf_path.replace(".pdf", "")}_page_{page_num + 1}.png'
        image_path = os.path.join(output_dir, image_filename)
        with open(image_path, 'wb') as f:
            f.write(img_data)
        all_metadata[pdf_path]['chunks'].append(convert_image_to_text(image_path, page_num + 1))
    except Exception as e:
        print(f"Error converting image chunk: {e}")
        return False

    return True

def ocr_text_image_extraction(page, page_num, all_metadata, output_dir, pdf_path):
    """
    Extract text and images from a page using OCR.
    Args: 
        page - current page processed
        all_metadata - all metadata of the patent
        output_dir - directory to save extracted images
    """

    # Page extraction pre - processing and cleaning:
    pix = page.get_pixmap(dpi=300)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    elif pix.n == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    img = cv2.GaussianBlur(img, (3, 3), 0)
    img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)  # or COLOR_RGBA2GRAY if needed

    _, img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Text extraction:
    reader = easyocr.Reader(['en'])
    ocr_results = reader.readtext(img)
    ocr_text = " ".join([result[1] for result in ocr_results])
    matches = re.findall(r'sheet\s+.+?\s+of\s+.+?(?=[\.\n]|$)', ocr_text, flags=re.IGNORECASE)

    if matches: 
        debug_print_chunking (False, add_image_chunk(page, page_num, all_metadata, output_dir, pdf_path))
    else:
        debug_print_chunking (add_text_chunk(ocr_text, page_num, all_metadata, output_dir, pdf_path), False)

def extract_text_and_images_from_patent(pdf_path, output_dir="extracted_images", enable_ocr=False):
    """
    Extract text and images from a patent PDF file.
    
    Args:
        pdf_path (str): Path to the patent PDF file
        output_dir (str): Directory to save extracted images
        enable_ocr (bool): Whether to use OCR for pages with minimal text (SLOW!)
    
    Returns:
        list: List of chunks with metadata in the format:
              {"type": "text" or "image", "page": page_number, "content": text or image_path}
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    all_metadata = {pdf_path: {
                      "chunks": []}}
    
    print(f"Processing {total_pages} pages...")
    
    for page_num in range(total_pages):
        page = doc[page_num]
        print(f"📄 Processing page {page_num + 1}/{total_pages}...", end=" ")
        
        # Extract text from the page
        text_content = page.get_text()
        if text_content.strip():
            matches = re.findall(r'sheet\s+.+?\s+of\s+.+?(?=[\.\n]|$)', text_content, flags=re.IGNORECASE)
            image_added = False
            text_added = False
            if matches:
                image_added = add_image_chunk(page, page_num, all_metadata, output_dir, pdf_path)
            else:
                text_added = add_text_chunk(text_content, page_num, all_metadata, output_dir, pdf_path)
            debug_print_chunking(text_added, image_added)
        # If no text is found, use OCR to extract text and images
        else:
            print("No text found, using OCR to extract text and images")
            ocr_text_image_extraction(page, page_num, all_metadata, output_dir, pdf_path)

    # Close the document
    doc.close()
    print(f"Extraction complete! Found {len([c for c in all_metadata[pdf_path]['chunks'] if c['type'] == 'text'])} text chunks and {len([c for c in all_metadata[pdf_path]['chunks'] if c['type'] == 'image'])} images.")
    
    return all_metadata

def save_chunks_metadata(chunks, metadata_file="all_metadata.json"):
    """
    Save the chunks metadata to a JSON file.
    If file exists, merge new data with existing data.
    
    Args:
        chunks (dict): Dictionary with PDF path as key and chunk data as value
        metadata_file (str): Path to save the metadata file
    """
    # Load existing data if file exists
    existing_data = {}
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            print(f"Loaded existing data from {metadata_file}")
        except (json.JSONDecodeError, Exception) as e:
            print(f"Warning: Could not load existing data ({e}), starting fresh")
            existing_data = {}
    
    # Merge new chunks with existing data
    existing_data.update(chunks)
    
    # Save combined data
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, indent=2, ensure_ascii=False)
        
    print(f"Metadata saved to {metadata_file}")

def load_chunks_metadata(metadata_file="all_metadata.json"):
    """
    Load chunks metadata from JSON file.
    
    Args:
        metadata_file (str): Path to the metadata file
        
    Returns:
        list: List of chunk dictionaries
    """
    if not os.path.exists(metadata_file):
        # Create empty JSON file if it doesn't exist
        print(f"Creating new metadata file: {metadata_file}")
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=2)
        return []
    
    # Context manager form - file always closed even if error
    with open(metadata_file, 'r', encoding='utf-8') as f:
        chunks = json.load(f)
    
    print(f"Loaded {len(chunks)} groups of chunks from {metadata_file}")
    return chunks

# === STEP 2: VECTOR STORE ===
def create_vector_store(chunks, model_name="all-MiniLM-L6-v2", collection_name="patent_chunks"):
    """
    Create vector store using SentenceTransformer and Qdrant.
    
    Args:
        chunks (list): List of chunk dictionaries
        model_name (str): SentenceTransformer model name 
                          (passed default "all-MiniLM-L6-v2" which is popular and balanced
                          embedding vector size 384)
        collection_name (str): Qdrant collection name
        
    Returns:
        tuple: (qdrant_client, sentence_transformer_model)
    """
    print(f"\n=== Step 2: Creating Vector Store ===")

    # Initialize SentenceTransformer
    print(f"Loading SentenceTransformer model: {model_name}")
    model = SentenceTransformer(model_name)
    
    # Extract text content for encoding
    texts = [chunk['content'] for chunk in chunks]
    
    # Create embeddings
    print("Creating embeddings for all text and image chunks...")
    embeddings = model.encode(texts, show_progress_bar=True)
    vector_size = embeddings.shape[1]
    print(f"Created embeddings: {embeddings.shape[0]} vectors of size {vector_size}")
    
    # Initialize in-memory (RAM) Qdrant client
    print("Setting up in-memory Qdrant vector database...")
    client = QdrantClient(":memory:")
    
    # Create collection:
    # 1. vectors_config: size=vector_size, distance=Distance.COSINE
    # 2. size: number of dimensions in the vector space
    # 3. distance: distance metric used for similarity search
    # 4. COSINE: cosine similarity
    # 5. id: unique identifier for each point
    # 6. vector: embedding vector
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )
    print(f"Created Qdrant collection: {collection_name}")
    
    # Prepare points for insertion
    points = []
    # Each chunk and its corresponding embedding are zipped together
    # and then enumerated to get the index and the chunk and embedding
    # the index is used to create a unique ID for each point
    # the chunk is used to create the payload
    # the embedding is used to create the vector
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        point = PointStruct(
            id=str(uuid.uuid4()),  # Unique ID for each point
            vector=embedding.tolist(),  # Convert numpy array to list
            payload={
                "type": chunk["type"],
                "page": chunk["page"],
                "content": chunk["content"],
                "chunk_index": i
            }
        )
        points.append(point)
    
    # Insert vectors into Qdrant
    client.upsert(
        collection_name=collection_name,
        points=points
    )
    
    print(f"✅ Stored {len(points)} vectors in Qdrant collection")
    print(f"✅ Vector store ready for semantic search!")
    
    return client, model

# === STEP 3: QUESTION INPUT ===
def load_questions(questions_file="questions.txt"):
    """
    Load questions from a text file.
    
    Args:
        questions_file (str): Path to the questions file
        
    Returns:
        list: List of question strings
    """
    print(f"\n=== Step 3: Loading Questions ===")
    
    # Check if questions file exists
    if not os.path.exists(questions_file):
        print(f"❌ Error: Questions file '{questions_file}' not found!")
        return []
    
    # Load questions from file
    inside_hidden = False
    count_hidden = 0
    questions = []
    try:
        with open(questions_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                question = line.strip()
                if question == "[[HIDDEN]]":
                    inside_hidden = True
                    count_hidden += 1
                    continue
                if question == "[[/HIDDEN]]":
                    inside_hidden = False
                    count_hidden += 1
                    continue
                if not inside_hidden:
                    questions.append(question)
                    print(f"  Q{line_num - count_hidden}: {question}")
        
        print(f"✅ Loaded {len(questions)} questions from '{questions_file}'")
        
    except Exception as e:
        print(f"❌ Error reading questions file: {e}")
        return []
    
    if not questions:
        print("⚠️  No questions found in file!")
        return []
    
    return questions

# === STEP 4: RAG PROMPT CONSTRUCTION ===
def retrieve_relevant_chunks(question, client, model, collection_name="patent_chunks", top_k=3):
    """
    Retrieve top-k relevant text chunks for a question using vector similarity.
    
    Args:
        question (str): The question to search for
        client: Qdrant client
        model: SentenceTransformer model
        collection_name (str): Name of Qdrant collection
        top_k (int): Number of chunks to retrieve
        
    Returns:
        list: List of relevant chunks with metadata including embeddings of the form:
                                {
                                    'content': str,
                                    'page': int,
                                    'chunk_index': int,
                                    'similarity': float,
                                    'embedding': list
                                }
    """
    # Convert question to embedding
    question_embedding = model.encode([question])

    # Search for similar chunks in Qdrant (with vectors) - using query_points (newer API)
    search_results = client.query_points(
        collection_name=collection_name,
        query=question_embedding[0].tolist(),
        limit=top_k,
        query_filter=Filter(
            must=[
                FieldCondition(key="type", match=MatchValue(value="text"))
            ]
        ),
        with_vectors=True  # Include vectors in results
    )
    
    # Extract chunks with similarity scores and embeddings
    relevant_chunks = []
    for result in search_results.points:
        relevant_chunks.append({
            'content': result.payload['content'],
            'page': result.payload['page'],
            'chunk_index': result.payload['chunk_index'],
            'similarity': result.score,
            'embedding': result.vector  # Include the stored embedding
        })
    
    return relevant_chunks


def top_similar_images(relevant_chunks, chunks, max_images=2, client=None, collection_name="patent_chunks"):
    """
    Find up to 2 most relevant image chunks based on similarity to the relevant text chunks.
    
    Args:
        relevant_chunks (list): Already retrieved relevant text chunks (with embeddings) of the form:
                                {
                                    'content': str,
                                    'page': int,
                                    'chunk_index': int,
                                    'similarity': float,
                                    'embedding': list
                                }
        chunks (list): All chunks (text and image)
        max_images (int): Maximum number of images to return
        client: Qdrant client
        
    Returns:
        dict of top-k most relevant image chunks of the form:
                                {
                                    'page': int,
                                    'content': str,
                                    'chunk_index': int,
                                    'similarity': float,
                                    'embedding': list
                                }
    """
    
    # Find image chunks, for candidate store only the page number then compare with client Qdrant.
    candidate_images = [chunk for chunk in chunks if chunk['type'] == 'image_description']
    
    if not candidate_images:
        return []
    
    # Use pre-computed embeddings from relevant chunks (no re-encoding!)
    relevant_text_embeddings = [chunk['embedding'] for chunk in relevant_chunks]
    

    # take the embeddings that match the candidate_images form client qdrant - using query_points (newer API)
    candidates_images_results = client.query_points(
        collection_name=collection_name,
        query=[0.0] * 384,  # Dummy vector (not used for filtering)
        limit=1000,  # Large limit to get all matches
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="page",
                    match=MatchAny(any=[img['page'] for img in candidate_images])
                ),
                FieldCondition(
                    key="type", 
                    match=MatchValue(value="image_description")
                )
            ]
        ), with_vectors=True )
    
    candidates_images_embeddings = []
    for result in candidates_images_results.points:
        candidates_images_embeddings.append({
            'page': result.payload['page'],
            'content': result.payload['content'],
            'chunk_index': result.payload['chunk_index'],
            'similarity': result.score,
            'embedding': result.vector
        })



    # Calculate max similarity between each image and any relevant text chunk
    similarities = []
    for candidate_embedding in candidates_images_embeddings:
        # Get similarity scores between this image and all relevant text chunks
        img_similarities = cosine_similarity([candidate_embedding['embedding']], relevant_text_embeddings)[0]
        # Take the maximum similarity (best match with any relevant text)
        max_similarity = max(img_similarities)
        similarities.append(max_similarity)
    
    # Add similarity scores to image data
    for i, img in enumerate(candidate_images):
        img['similarity'] = similarities[i]
    
    # Sort by similarity (highest first) and return top max_images
    candidate_images.sort(key=lambda x: x['similarity'], reverse=True)
    selected_images = candidate_images[:max_images]
    
    # Debug: Print similarity scores
    print(f"     Top {max_images} image similarity scores (vs pre-computed relevant text embeddings):")
    for i, img in enumerate(selected_images):
        print(f"       Image {i+1}: Page {img['page']}, Max Similarity = {img['similarity']:.3f}, Path = {img['image_path']}")
    
    return selected_images


def construct_rag_prompt(question, question_index, relevant_chunks, selected_images_chunks, max_context_bytes=2000):
    """
    Construct RAG prompt with question, context, and images.
    
    Args:
        question (str): The question
        relevant_chunks (list): Retrieved text chunks
        selected_images (list): Paths to relevant images
        max_context_bytes (int): Maximum context length in bytes
        
    Returns:
        str1: Formatted prompt for Llava
        str2: Formatted prompt for Llama
    """
    # Sort relevant chunks by similarity (highest first)
    relevant_chunks.sort(key=lambda x: x['similarity'], reverse=True)
    # Add relevant chunks to the context, but not exceeding the max_context_bytes limit
    context_parts = []
    total_bytes = 0
    for chunk in relevant_chunks:
        chunk_text = chunk['content']
        chunk_bytes = len(chunk_text.encode('utf-8'))
        
        # Check if adding this chunk would exceed limit
        if total_bytes + chunk_bytes <= max_context_bytes:
            context_parts.append(f"[Page {chunk['page']}] {chunk_text}")
            total_bytes += chunk_bytes
        else:
            # Add partial chunk to reach exactly max_context_bytes
            remaining_bytes = max_context_bytes - total_bytes
            if remaining_bytes > 50:  # Only add if meaningful amount remaining
                # encode for snniping the exact amount of bytes, then decode to utf-8 back.
                partial_text = chunk_text.encode('utf-8')[:remaining_bytes].decode('utf-8', errors='ignore')
                context_parts.append(f"[Page {chunk['page']}] {partial_text}")
            break

    question_bytes = len(question.encode('utf-8'))
    if selected_images_chunks:
        images_context = []
        image_list = ""
        for index, image_chunk in enumerate(selected_images_chunks):
            image_list += f"\nImage {index+1}: {image_chunk['image_path']}"
            images_context.append(f"\nImage {index+1}-{image_chunk['content']}")
        images_list_bytes = len("".join(image_list).encode('utf-8'))
        images_context_bytes = len("".join(images_context).encode('utf-8'))
        
        # Join the context parts with newlines.
        text_context = "\n".join(context_parts)

        # Construct final prompt for Llava
        prompt_llava = f"""Question {question_index} [bytes: {question_bytes}]:\n{question}\nText-Context [bytes: {max_context_bytes - images_list_bytes - question_bytes}]:\n{text_context.encode('utf-8')[:max_context_bytes - images_list_bytes - question_bytes].decode('utf-8', errors='ignore')}\nImages-Paths[bytes: {images_list_bytes}]: {image_list}"""

        # Build context from relevant chunks for Llama:
        images_context = "".join(images_context)
        context_bytes_with_images = max_context_bytes - images_context_bytes - question_bytes
        prompt_llama = f"""Question {question_index} [bytes: {question_bytes}]:\n{question}\nText-Context [bytes: {context_bytes_with_images}]:\n{text_context.encode('utf-8')[:context_bytes_with_images].decode('utf-8', errors='ignore')}\nImages-Context [bytes: {images_context_bytes}]:\n{images_context}"""
    else:
        prompt_llava = None
        context_bytes_without_images = max_context_bytes - question_bytes
        prompt_llama = f"""Question {question_index} [bytes: {question_bytes}]:\n{question}\nText-Context [bytes: {context_bytes_without_images}]:\n{text_context.encode('utf-8')[:context_bytes_without_images].decode('utf-8', errors='ignore')}"""    
    
    return prompt_llava, prompt_llama

# Using the models based on the question prompt.
def process_questions_with_rag(questions, chunks, client, model):
    """
    Process all questions using RAG pipeline. (retrieve relevant chunks, top similar images, construct rag prompt)
    
    Args:
        questions (list): List of questions
        chunks (list): All chunks (text and image)
        client: Qdrant client 
        model: SentenceTransformer model
        
    Returns:
        list: List of constructed prompts of the form:
                                {
                                    'question': str,
                                    'llava_prompt': str,
                                    'llama_prompt': str,
                                    'relevant_pages': list,
                                    'selected_images_chunks': list
                                }
    """
    print(f"\n=== Step 4: RAG Prompt Construction ===")
    print(f"Processing {len(questions)} questions...")
    
    # Clear prompt files at the start of each run
    with open("prompt_llama.txt", "w") as f:
        f.write("")  # Clear the file
    with open("prompt_llava.txt", "w") as f:
        f.write("")  # Clear the file
    
    prompts = []
    
    for i, question in enumerate(questions, 1):
        print(f"\n🔍 Processing Question {i}/{len(questions)}: '{question[:50]}...'")
        
        # 1. Retrieve top-k relevant text chunks
        relevant_chunks = retrieve_relevant_chunks(question, client, model, top_k=3)
        print(f"   Retrieved {len(relevant_chunks)} relevant chunks")
        
        # Show text similarity scores
        for j, chunk in enumerate(relevant_chunks):
            print(f"     Chunk {j+1}: Page {chunk['page']}, Similarity = {chunk['similarity']:.3f}")
        
        # 2. Find nearby images using similarity scoring with relevant text
        relevant_pages = [chunk['page'] for chunk in relevant_chunks]
        selected_images_chunks = top_similar_images(relevant_chunks,chunks, max_images=2, client=client)
        
        # 3. Construct prompt
        llava_prompt, llama_prompt = construct_rag_prompt(question, i, relevant_chunks, selected_images_chunks)
        prompts.append({
            'question': question,
            'llava_prompt': llava_prompt,
            'llama_prompt': llama_prompt,
            'relevant_pages': relevant_pages,
            'selected_images_chunks': selected_images_chunks
        })
        
    print(f"\n✅ Constructed {len(prompts)} RAG prompts")
    return prompts

# === STEP 5: ANSWER GENERATION ===
def call_ollama_llama(prompt, model="llama3.2:3b", max_chars=300):
    """
    Call LLaMA via ollama for text-only questions.
    
    Args:
        prompt (str): The input prompt
        model (str): LLaMA model to use
        max_chars (int): Maximum characters for the answer
        
    Returns:
        str: Generated answer
    """
    try:
        # Prepare the command to call ollama
        cmd = ["ollama", "run", model]
        
        # Add instruction to limit response length
        full_prompt = f"""{prompt}

Please provide a concise answer based ONLY on the provided context. Do not use external knowledge. Keep your answer under {max_chars} characters."""
        
        # Use subprocess to call ollama
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        with open("prompt_llama.txt", "a") as f:
            f.write(full_prompt + "\n\n")
        # Send prompt and get response
        stdout, stderr = process.communicate(input=full_prompt, timeout=60)
        
        if process.returncode != 0:
            print(f"❌ Error calling ollama: {stderr}")
            return "Error: Unable to generate answer"
        
        # Clean and truncate the response
        answer = stdout.strip()
        if len(answer) > max_chars:
            answer = answer[:max_chars].rsplit(' ', 1)[0] + "..."
        
        return answer
        
    except subprocess.TimeoutExpired:
        print("❌ Timeout calling ollama")
        return "Error: Timeout generating answer"
    except Exception as e:
        print(f"❌ Error calling ollama: {e}")
        return "Error: Unable to generate answer"


def call_ollama_llava(prompt, model="llava:7b", max_chars=300):
    """
    Call LLaVA via ollama for text and image questions.
    
    Args:
        prompt (str): The input prompt
        model (str): LLaVA model to use
        max_chars (int): Maximum characters for the answer
    """

    try:
        cmd = ["ollama", "run", model]
        
        full_prompt = f"""{prompt}
Please provide a concise answer based ONLY on the provided context. Do not use external knowledge. Keep your answer under {max_chars} characters."""
        
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        
        with open("prompt_llava.txt", "a") as f:
            f.write(full_prompt + "\n\n")

        stdout, stderr = process.communicate(input=full_prompt, timeout=120)
        
        if process.returncode != 0:
            print(f"❌ Error calling ollama llava: {stderr}")
            return 
        
        answer = stdout.strip()
        if len(answer) > max_chars:
            answer = answer[:max_chars].rsplit(' ', 1)[0] + "..."
        return answer
    
    except subprocess.TimeoutExpired:
        print("❌ Timeout calling ollama llava")
        return 
    except Exception as e:
        print(f"❌ Error calling ollama llava: {e}")
        return 


def convert_image_to_text(image_path, page_num, model="llava:7b", max_chars=300):
    """
    Call LLaVA via ollama for image text conversion.
    
    Args:
        image_path (str): The input image path
        model (str): LLaVA model to use
        
    Returns:
        str: Generated answer
    """
    try:
        # Build the command with image paths
        cmd = ["ollama", "run", model]
        
        # Add instruction to limit response length and focus on provided content
        full_prompt = f"""
                        Please analyze the provided image. Keep your answer under {max_chars} characters. Base your answer ONLY on the provided image - do not use external knowledge.
                        Image:
                        {image_path}"""
                        
           
        # If we have images, add them to the prompt
        if image_path:
            # Convert to absolute paths
            abs_image_path = os.path.abspath(image_path) if os.path.exists(image_path) else None
            if abs_image_path:
                # Format images for LLaVA - this format depends on how ollama handles images
                image_section = "Image to analyze:\n" + abs_image_path + "\n\n"
                full_prompt = image_section + full_prompt
        
        # Use subprocess to call ollama
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        
        # Send prompt and get response
        stdout, stderr = process.communicate(input=full_prompt, timeout=120)
        
        if process.returncode != 0:
            print(f"❌ Error calling ollama llava: {stderr}")
            # Fallback to text-only if image processing fails
            print("   Falling back to text-only LLaMA...")
            return 
        
        # Clean and truncate the response
        answer = stdout.strip()
        return {
        "type": "image_description",
        "page": page_num,
        "content": answer[:max_chars].rsplit(' ', 1)[0] + "...",
        "image_path": image_path  # Keep original path for find_nearby_images
    }
        
    except subprocess.TimeoutExpired:
        print("❌ Timeout calling ollama llava")
        return 
    except Exception as e:
        print(f"❌ Error calling ollama llava: {e}")
        return 


def generate_answers(rag_prompts, output_file="answers.txt"):
    """
    Generate answers for all questions using ollama (LLaMA/LLaVA).
    
    Args:
        rag_prompts (list): List of RAG prompt dictionaries
        output_file (str): File to save answers
        
    Returns:
        list: List of answers
    """
    print(f"\n=== Step 5: Answer Generation ===")
    print(f"Generating answers for {len(rag_prompts)} questions using ollama...")
    
    answers = []
    
    # Check if ollama is available and test models
    try:
        result = subprocess.run(["ollama", "--version"], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print("❌ Error: ollama is not available or not working properly")
            return []
        
        # Test available models
        models = test_ollama_models()
        if not models['llama']:
            print("⚠️  Warning: No LLaMA model found. You may need to run 'ollama pull llama3.2'")
        if not models['llava']:
            print("⚠️  Warning: No LLaVA model found. You may need to run 'ollama pull llava'")
            
    except Exception as e:
        print(f"❌ Error: Cannot access ollama - {e}")
        print("   Please make sure ollama is installed and running")
        return []
    
        #     prompts.append({
        #     'question': question,
        #     'llava_prompt': llava_prompt,
        #     'llama_prompt': llama_prompt,
        #     'relevant_pages': relevant_pages,
        #     'selected_images_chunks': selected_images_chunks
        # })


    # Process each question
    for i, prompt_data in enumerate(rag_prompts, 1):
        question = prompt_data['question']
        llava_prompt = prompt_data['llava_prompt']
        llama_prompt = prompt_data['llama_prompt']
        # Extract image paths safely (handle cases with 0, 1, or 2+ images)
        selected_images = prompt_data['selected_images_chunks']
        image_paths = [img['image_path'] for img in selected_images] if selected_images else []
        
        print(f"\n🤖 Generating answer {i}/{len(rag_prompts)}")
        print(f"   Question: {question[:60]}...")
        
        # Choose model based on whether we have images 
        # ( We will use both Llama and Llava for image questions and Llama only for text questions)
        # if image_paths and len(image_paths) > 0:
        print(f"   Images include, using LLaVA with {len(image_paths)} images: {image_paths}")
        answer_llava = call_ollama_llava(llava_prompt)
        answer_llama = call_ollama_llama(llama_prompt)
        
        # TODO: compare answers
        # answer = compare_answers(answer_llama, answer_llava)

        # Ensure answers don't exceed 300 characters and handle None values
        if answer_llama and len(answer_llama) > 300:
            answer_llama = answer_llama[:297] + "..."
        if answer_llava and len(answer_llava) > 300:
            answer_llava = answer_llava[:297] + "..."
        
        # Handle None values for character counting
        llama_chars = len(answer_llama) if answer_llama else 0
        llava_chars = len(answer_llava) if answer_llava else 0
        
        answers.append({
            'question_number': i,
            'question': question,
            'answer_llama': answer_llama or "Error: LLaMA failed",
            'answer_llava': answer_llava or "Error: LLaVA failed", 
            'char_count_llama': llama_chars,
            'char_count_llava': llava_chars
        })
        
        print(f"Answer LLaVA ({llava_chars} chars):\n{answer_llava}")
        print(f"Answer LLaMA ({llama_chars} chars):\n{answer_llama}")
    
    # Save answers to file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for ans_data in answers:
                f.write(f"Question {ans_data['question_number']}: {ans_data['question']}\n")
                f.write(f"{ans_data['answer']}\n\n")
        
        print(f"\n✅ Answers saved to {output_file}")
        
        # Show summary
        avg_length = sum(a['char_count'] for a in answers) / len(answers)
        max_length = max(a['char_count'] for a in answers)
        print(f"   Total answers: {len(answers)}")
        print(f"   Average length: {avg_length:.1f} characters")
        print(f"   Maximum length: {max_length} characters")
        
    except Exception as e:
        print(f"❌ Error saving answers: {e}")
    
    return answers


def test_ollama_models():
    """
    Test if required ollama models are available.
    
    Returns:
        dict: Status of available models
    """
    print("🔍 Testing ollama model availability...")
    
    models = {
        'llama': False,
        'llava': False
    }
    
    try:
        # Check available models
        result = subprocess.run(["ollama", "list"], 
                              capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            output = result.stdout.lower()
            
            # Check for LLaMA variants
            if any(model in output for model in ['llama3.2:3b', 'llama', 'llama3', 'llama2']):
                models['llama'] = True
                print("   ✅ LLaMA model found")
            else:
                print("   ⚠️  No LLaMA model found")
            
            # Check for LLaVA
            if any(model in output for model in ['llava:7b', 'llava']):
                models['llava'] = True
                print("   ✅ LLaVA model found")
            else:
                print("   ⚠️  No LLaVA model found")
                
            print(f"   Available models: {result.stdout.strip()}")
        else:
            print(f"   ❌ Error listing models: {result.stderr}")
            
    except Exception as e:
        print(f"   ❌ Error testing ollama: {e}")
    
    return models


def main():
    """
    Main function to execute the RAG pipeline steps
    """
    # pdf switch
    pdf_path = "patent_1.pdf"
    
    # Check if patent PDF exists
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found in the current directory.")
        return
    
    print("=== RAG Pipeline for Patent Analysis ===")
    print(f"Processing: {pdf_path}\n")
    
    # === STEP 1: CHUNKING ===
    print("=== Step 1: Chunking the Patent ===")
    
    # Check if we already have processed any chunks
    all_metadata = load_chunks_metadata()
    if pdf_path in all_metadata:
        print(f"Loaded existing chunks for {pdf_path}")
        chunks = all_metadata[pdf_path]["chunks"]
    else:
        print("Processing patent PDF...")
        print("💡 For faster processing, OCR is disabled by default")
        print("   If you need OCR for scanned pages, set enable_ocr=True in the function call")
        all_metadata = extract_text_and_images_from_patent(pdf_path, enable_ocr=False)
        save_chunks_metadata(all_metadata)
        chunks = all_metadata[pdf_path]["chunks"]
    
    # Print Step 1 summary
    text_chunks = [c for c in chunks if c['type'] == 'text']
    image_chunks = [c for c in chunks if c['type'] == 'image_description']
    
    print(f"\n=== Step 1 Summary ===")
    print(f"Total chunks: {len(chunks)}")
    print(f"Text chunks: {len(text_chunks)}")
    print(f"Image chunks: {len(image_chunks)}")
    
    # === STEP 2: VECTOR STORE ===
    client, model = create_vector_store(chunks)
    
    # === STEP 3: QUESTION INPUT ===
    questions = load_questions()
    
    # === STEP 4: RAG PROMPT CONSTRUCTION ===
    if questions:  # Only proceed if we have questions
        rag_prompts = process_questions_with_rag(questions, chunks, client, model)
    else:
        print("⚠️  No questions to process - skipping RAG prompt construction")
        rag_prompts = []
    
    # === STEP 5: ANSWER GENERATION ===
    answers = []
    if rag_prompts:  # Only proceed if we have prompts
        answers = generate_answers(rag_prompts)
    else:
        print("⚠️  No prompts to process - skipping answer generation")
    
    print(f"\n=== Pipeline Complete ===")
    print(f"✅ Step 1: Patent chunked into {len(chunks)} pieces")
    print(f"✅ Step 2: {len(text_chunks)} text chunks vectorized and stored")
    print(f"✅ Step 3: {len(questions)} questions loaded and ready")
    print(f"✅ Step 4: {len(rag_prompts)} RAG prompts constructed")
    print(f"✅ Step 5: {len(answers)} answers generated and saved")
    
    return chunks, client, model, questions, rag_prompts, answers
    


if __name__ == "__main__":
    main()
