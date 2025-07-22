import os
import subprocess
import fitz  # PyMuPDF
import json
from PIL import Image
import io
import tempfile
import easyocr
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
import uuid

# === STEP 1: CHUNKING ===
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
    
    # Initialize OCR reader only if needed
    reader = None
    if enable_ocr:
        print("⚠️  OCR enabled - this will be SLOW on CPU!")
        reader = easyocr.Reader(['en'])
    
    # Open the PDF using PyMuPDF for text extraction
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    chunks = []
    
    print(f"Processing {total_pages} pages...")
    
    for page_num in range(total_pages):
        page = doc[page_num]
        print(f"📄 Processing page {page_num + 1}/{total_pages}...", end=" ")
        
        # Extract text from the page
        text_content = page.get_text()
        
        # If direct text extraction is empty or minimal, use OCR (if enabled)
        if len(text_content.strip()) < 50 and enable_ocr and reader:
            print("(using OCR - this may take 10-30 seconds)", end=" ")
        # Converting page to image for OCR:
            # Using get_pixmap to convert the page to a PNG image
            pix = page.get_pixmap()
            # tobytes() to convert the image to bytes
            img_data = pix.tobytes("png")
            # Image.open() to open the image
            img = Image.open(io.BytesIO(img_data))
            
            # Use OCR to extract text
            # reader.readtext() to extract text from the image
            ocr_results = reader.readtext(img_data)
            # " ".join([result[1] for result in ocr_results]) to join the text into a single string
            # result is a tuple of
            ocr_text = " ".join([result[1] for result in ocr_results])
            
            # Combine original text with OCR results (append, don't override)
            if ocr_text.strip():
                text_content = text_content + " " + ocr_text
        elif len(text_content.strip()) < 50:
            print("(minimal text, OCR disabled)", end=" ")
        
        # Add text chunk if there's content
        text_added = False
        if text_content.strip():
            chunks.append({
                "type": "text",
                "page": page_num + 1,
                "content": text_content.strip()
            })
            text_added = True
        
        # Extract images from the page (only if 'FIG & sheet' keywords is present)
        image_list = page.get_images(full=True)
        page_text_lower = text_content.lower()
        has_fig_sheet_keyword = 'fig' in page_text_lower and 'sheet' in page_text_lower
        images_added = 0
    
        for img_index, img in enumerate(image_list):
            # Only process images if 'FIG & sheet' keywords is present
            if not has_fig_sheet_keyword:
                continue
                
            try:
                # Get the XREF of the image
                xref = img[0]
                    
                # Extract the image data
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                    
                # Create a unique filename for the image
                image_filename = f"page_{page_num + 1}_img_{img_index + 1}.{image_ext}"
                image_path = os.path.join(output_dir, image_filename)
                    
                # Save the image
                with open(image_path, "wb") as img_file:
                    img_file.write(image_bytes)
                    
                # Add image chunk
                chunks.append({
                    "type": "image",
                    "page": page_num + 1,
                    "content": image_path
                })
                images_added += 1
                    
            except Exception as e:
                print(f"  Error extracting image {img_index + 1} from page {page_num + 1}: {e}")
                continue
        
        # Progress summary for this page
        summary = []
        if text_added:
            summary.append("✅ text")
        if images_added > 0:
            summary.append(f"✅ {images_added} images")
        if not text_added and images_added == 0:
            summary.append("⚪ skipped")
        
        print(f"({', '.join(summary)})")
        
    # Close the document
    doc.close()
    
    print(f"Extraction complete! Found {len([c for c in chunks if c['type'] == 'text'])} text chunks and {len([c for c in chunks if c['type'] == 'image'])} images.")
    
    return chunks


def save_chunks_metadata(chunks, metadata_file="chunks_metadata.json"):
    """
    Save the chunks metadata to a JSON file.
    
    Args:
        chunks (list): List of chunk dictionaries
        metadata_file (str): Path to save the metadata file
    """
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)
    
    print(f"Metadata saved to {metadata_file}")


def load_chunks_metadata(metadata_file="chunks_metadata.json"):
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
            json.dump([], f, indent=2)
        return []
    
    # Context manager form - file always closed even if error
    with open(metadata_file, 'r', encoding='utf-8') as f:
        chunks = json.load(f)
    
    print(f"Loaded {len(chunks)} chunks from {metadata_file}")
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
    
    # Filter only text chunks
    text_chunks = [chunk for chunk in chunks if chunk['type'] == 'text']
    print(f"Found {len(text_chunks)} text chunks to encode")
    
    # Initialize SentenceTransformer
    print(f"Loading SentenceTransformer model: {model_name}")
    model = SentenceTransformer(model_name)
    
    # Extract text content for encoding
    texts = [chunk['content'] for chunk in text_chunks]
    
    # Create embeddings
    print("Creating embeddings for text chunks...")
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
    for i, (chunk, embedding) in enumerate(zip(text_chunks, embeddings)):
        point = PointStruct(
            id=str(uuid.uuid4()),  # Unique ID for each point
            vector=embedding.tolist(),  # Convert numpy array to list
            payload={
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
    questions = []
    try:
        with open(questions_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                question = line.strip()
                if question:  # Skip empty lines
                    questions.append(question)
                    print(f"  Q{line_num}: {question}")
        
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
        list: List of relevant chunks with metadata
    """
    # Convert question to embedding
    question_embedding = model.encode([question])
    
    # Search for similar chunks in Qdrant
    search_results = client.search(
        collection_name=collection_name,
        query_vector=question_embedding[0].tolist(),
        limit=top_k
    )
    
    # Extract chunks with similarity scores
    relevant_chunks = []
    for result in search_results:
        relevant_chunks.append({
            'content': result.payload['content'],
            'page': result.payload['page'],
            'chunk_index': result.payload['chunk_index'],
            'similarity': result.score
        })
    
    return relevant_chunks


def find_nearby_images(relevant_pages, all_chunks, max_images=2):
    """
    Find up to 2 nearby image chunks from the same or adjacent pages.
    
    Args:
        relevant_pages (list): List of page numbers from relevant text chunks
        all_chunks (list): All chunks (text and image)
        max_images (int): Maximum number of images to return
        
    Returns:
        list: List of image paths
    """
    if not relevant_pages:
        return []
    
    # Get all unique pages + adjacent pages
    target_pages = set()
    for page in relevant_pages:
        target_pages.add(page)           # Same page
        target_pages.add(page - 1)       # Previous page
        target_pages.add(page + 1)       # Next page
    
    # Find image chunks from target pages
    image_chunks = []
    for chunk in all_chunks:
        if (chunk['type'] == 'image' and 
            chunk['page'] in target_pages):
            image_chunks.append({
                'path': chunk['content'],
                'page': chunk['page']
            })
    
    # Sort by page number for consistent ordering
    image_chunks.sort(key=lambda x: x['page'])
    
    # Return up to max_images
    selected_images = image_chunks[:max_images]
    return [img['path'] for img in selected_images]


def construct_rag_prompt(question, relevant_chunks, image_paths, max_context_bytes=2000):
    """
    Construct RAG prompt with question, context, and images.
    
    Args:
        question (str): The question
        relevant_chunks (list): Retrieved text chunks
        image_paths (list): Paths to relevant images
        max_context_bytes (int): Maximum context length in bytes
        
    Returns:
        str: Formatted prompt
    """
    # Build context from relevant chunks
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
    
    # Join the context parts with newlines.
    context = "\n\n".join(context_parts)
    
    # Format images (up to 2)
    image_list = ", ".join(image_paths[:2]) if image_paths else "None"
    
    # Construct final prompt
    prompt = f"""Question: {question}

Context:
{context}

Images:
{image_list}"""
    
    return prompt


def process_questions_with_rag(questions, chunks, client, model):
    """
    Process all questions using RAG pipeline.
    
    Args:
        questions (list): List of questions
        chunks (list): All chunks (text and image)
        client: Qdrant client
        model: SentenceTransformer model
        
    Returns:
        list: List of constructed prompts
    """
    print(f"\n=== Step 4: RAG Prompt Construction ===")
    print(f"Processing {len(questions)} questions...")
    
    prompts = []
    
    for i, question in enumerate(questions, 1):
        print(f"\n🔍 Processing Question {i}/{len(questions)}: '{question[:50]}...'")
        
        # 1. Retrieve top-k relevant text chunks
        relevant_chunks = retrieve_relevant_chunks(question, client, model, top_k=3)
        print(f"   Retrieved {len(relevant_chunks)} relevant chunks")
        
        # Show similarity scores
        for j, chunk in enumerate(relevant_chunks):
            print(f"     Chunk {j+1}: Page {chunk['page']}, Similarity = {chunk['similarity']:.3f}")
        
        # 2. Find nearby images
        relevant_pages = [chunk['page'] for chunk in relevant_chunks]
        image_paths = find_nearby_images(relevant_pages, chunks, max_images=2)
        print(f"   Found {len(image_paths)} nearby images: {image_paths}")
        
        # 3. Construct prompt
        prompt = construct_rag_prompt(question, relevant_chunks, image_paths)
        prompts.append({
            'question': question,
            'prompt': prompt,
            'relevant_pages': relevant_pages,
            'image_paths': image_paths
        })
        
        # Show prompt preview
        prompt_preview = prompt.replace('\n', ' ')[:150]
        print(f"   Prompt preview: '{prompt_preview}...'")
    
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


def call_ollama_llava(prompt, image_paths, model="llava:7b", max_chars=300):
    """
    Call LLaVA via ollama for questions with images.
    
    Args:
        prompt (str): The input prompt
        image_paths (list): List of image file paths
        model (str): LLaVA model to use
        max_chars (int): Maximum characters for the answer
        
    Returns:
        str: Generated answer
    """
    try:
        # Build the command with image paths
        cmd = ["ollama", "run", model]
        
        # Add instruction to limit response length and focus on provided content
        full_prompt = f"""{prompt}

Please analyze the provided images and text context to answer the question. Base your answer ONLY on the provided images and context - do not use external knowledge. Keep your answer under {max_chars} characters."""
        
        # For ollama with LLaVA, we need to provide images as command line arguments or in a specific format
        # Let's try the approach where we send the prompt with image paths in the stdin
        prompt_with_images = full_prompt
        
        # If we have images, add them to the prompt
        if image_paths:
            # Convert to absolute paths
            abs_image_paths = [os.path.abspath(path) for path in image_paths[:2] if os.path.exists(path)]
            if abs_image_paths:
                # Format images for LLaVA - this format depends on how ollama handles images
                image_section = "Images to analyze:\n" + "\n".join(abs_image_paths) + "\n\n"
                prompt_with_images = image_section + full_prompt
        
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
        stdout, stderr = process.communicate(input=prompt_with_images, timeout=120)
        
        if process.returncode != 0:
            print(f"❌ Error calling ollama llava: {stderr}")
            # Fallback to text-only if image processing fails
            print("   Falling back to text-only LLaMA...")
            return call_ollama_llama(prompt, max_chars=max_chars)
        
        # Clean and truncate the response
        answer = stdout.strip()
        if len(answer) > max_chars:
            answer = answer[:max_chars].rsplit(' ', 1)[0] + "..."
        
        return answer
        
    except subprocess.TimeoutExpired:
        print("❌ Timeout calling ollama llava")
        # Fallback to text-only
        print("   Falling back to text-only LLaMA...")
        return call_ollama_llama(prompt, max_chars=max_chars)
    except Exception as e:
        print(f"❌ Error calling ollama llava: {e}")
        # Fallback to text-only
        print("   Falling back to text-only LLaMA...")
        return call_ollama_llama(prompt, max_chars=max_chars)


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
    
    # Process each question
    for i, prompt_data in enumerate(rag_prompts, 1):
        question = prompt_data['question']
        prompt = prompt_data['prompt']
        image_paths = prompt_data['image_paths']
        
        print(f"\n🤖 Generating answer {i}/{len(rag_prompts)}")
        print(f"   Question: {question[:60]}...")
        
        # Choose model based on whether we have images
        if image_paths and len(image_paths) > 0:
            print(f"   Using LLaVA with {len(image_paths)} images: {image_paths}")
            answer = call_ollama_llava(prompt, image_paths)
        else:
            print(f"   Using LLaMA (text-only)")
            answer = call_ollama_llama(prompt)
        
        # Ensure answer doesn't exceed 300 characters
        if len(answer) > 300:
            answer = answer[:297] + "..."
        
        answers.append({
            'question_number': i,
            'question': question,
            'answer': answer,
            'char_count': len(answer)
        })
        
        print(f"   Answer ({len(answer)} chars): {answer[:100]}...")
    
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


def run_step5_only(questions_file="questions.txt", chunks_file="chunks_metadata.json", output_file="answers.txt"):
    """
    Run only Step 5 (Answer Generation) using existing data.
    Useful for testing or re-running just the answer generation.
    
    Args:
        questions_file (str): Path to questions file
        chunks_file (str): Path to chunks metadata file
        output_file (str): Path to save answers
    """
    print("=== Running Step 5 Only: Answer Generation ===")
    
    # Load existing data
    chunks = load_chunks_metadata(chunks_file)
    questions = load_questions(questions_file)
    
    if not chunks:
        print("❌ No chunks found. Please run Steps 1-4 first.")
        return
    
    if not questions:
        print("❌ No questions found.")
        return
    
    # Create vector store (Steps 2-4)
    client, model = create_vector_store(chunks)
    rag_prompts = process_questions_with_rag(questions, chunks, client, model)
    
    # Generate answers (Step 5)
    answers = generate_answers(rag_prompts, output_file)
    
    print(f"\n✅ Step 5 Complete: {len(answers)} answers generated")
    return answers


def main():
    """
    Main function to execute the RAG pipeline steps
    """
    pdf_path = "patent.pdf"
    
    # Check if patent PDF exists
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found in the current directory.")
        return
    
    print("=== RAG Pipeline for Patent Analysis ===")
    print(f"Processing: {pdf_path}\n")
    
    # === STEP 1: CHUNKING ===
    print("=== Step 1: Chunking the Patent ===")
    
    # Check if we already have processed chunks
    if os.path.exists("chunks_metadata.json"):
        print("Found existing chunks_metadata.json - loading...")
        chunks = load_chunks_metadata()
    else:
        print("Processing patent PDF...")
        print("💡 For faster processing, OCR is disabled by default")
        print("   If you need OCR for scanned pages, set enable_ocr=True in the function call")
        chunks = extract_text_and_images_from_patent(pdf_path, enable_ocr=True)
        save_chunks_metadata(chunks)
    
    # Print Step 1 summary
    text_chunks = [c for c in chunks if c['type'] == 'text']
    image_chunks = [c for c in chunks if c['type'] == 'image']
    
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
