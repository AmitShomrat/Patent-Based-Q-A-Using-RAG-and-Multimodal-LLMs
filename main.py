import os
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


def extract_text_and_images_from_patent(pdf_path, output_dir="extracted_images"):
    """
    Extract text and images from a patent PDF file.
    
    Args:
        pdf_path (str): Path to the patent PDF file
        output_dir (str): Directory to save extracted images
    
    Returns:
        list: List of chunks with metadata in the format:
              {"type": "text" or "image", "page": page_number, "content": text or image_path}
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize OCR reader
    reader = easyocr.Reader(['en'])
    
    # Open the PDF
    doc = fitz.open(pdf_path)
    chunks = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # Extract text from the page
        text_content = page.get_text()
        
        # If direct text extraction is empty or minimal, use OCR
        if len(text_content.strip()) < 50:
            # Convert page to image for OCR
            pix = page.get_pixmap()
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            
            # Use OCR to extract text
            ocr_results = reader.readtext(img_data)
            ocr_text = " ".join([result[1] for result in ocr_results])
            
            # Combine original text with OCR results (append, don't override)
            if ocr_text.strip():
                text_content = text_content + " " + ocr_text
        
        # Add text chunk if there's content
        if text_content.strip():
            chunks.append({
                "type": "text",
                "page": page_num + 1,
                "content": text_content.strip()
            })
        
        # Extract images from the page (only if 'FIG' keyword is present)
        image_list = page.get_images(full=True)
        
        # Check if page contains 'FIG' keyword (case insensitive)
        page_text_lower = text_content.lower()
        has_fig_sheet_keyword = 'fig' in page_text_lower and 'sheet' in page_text_lower
    
        for img_index, img in enumerate(image_list):
            # Only process images if 'FIG' keyword is present
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
                    
            except Exception as e:
                print(f"  Error extracting image {img_index + 1} from page {page_num + 1}: {e}")
                continue
        
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
    with open(metadata_file, 'r', encoding='utf-8') as f:
        chunks = json.load(f)
    
    print(f"Loaded {len(chunks)} chunks from {metadata_file}")
    return chunks


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
    
    # Initialize in-memory Qdrant client
    print("Setting up in-memory Qdrant vector database...")
    client = QdrantClient(":memory:")
    
    # Create collection
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )
    print(f"Created Qdrant collection: {collection_name}")
    
    # Prepare points for insertion
    points = []
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
        chunks = extract_text_and_images_from_patent(pdf_path)
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
    
    print(f"\n=== Pipeline Status ===")
    print(f"✅ Step 1: Patent chunked into {len(chunks)} pieces")
    print(f"✅ Step 2: {len(text_chunks)} text chunks vectorized and stored")
    print(f"✅ Step 3: {len(questions)} questions loaded and ready")
    print(f"🔄 Next: Step 4 (RAG Prompt Construction), Step 5 (Answer Generation)")
    
    return chunks, client, model, questions
    


if __name__ == "__main__":
    main()
