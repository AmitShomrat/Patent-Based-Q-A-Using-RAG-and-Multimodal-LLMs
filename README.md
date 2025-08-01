# RAG Pipeline for Patent Analysis

A comprehensive Retrieval-Augmented Generation (RAG) system designed to analyze patent documents and answer questions using both text and image content. This system combines multiple AI models to provide accurate, context-aware responses about patent information.

## 🎯 Overview

This project implements a complete RAG pipeline that:
- **Processes patent PDFs** to extract text and images
- **Creates vector embeddings** for semantic search
- **Generates contextual answers** using LLaMA and LLaVA models
- **Evaluates answer quality** through semantic similarity analysis
- **Selects best responses** automatically based on performance metrics

## ✨ Features

### 📄 Document Processing
- **Multi-modal extraction**: Text and image content from PDF patents
- **OCR support**: Handles scanned pages with EasyOCR
- **Smart chunking**: Separates text content from technical diagrams
- **Metadata preservation**: Maintains page references and content types

### 🔍 Vector Search
- **Semantic embeddings**: Uses SentenceTransformer models
- **In-memory vector store**: Powered by Qdrant for fast retrieval
- **Context-aware search**: Finds relevant text and related images
- **Similarity ranking**: Returns top-k most relevant chunks

### 🤖 AI-Powered Answers
- **Dual model support**: LLaMA (text) and LLaVA (multimodal)
- **RAG prompts**: Combines questions with relevant context
- **Ollama integration**: Local model execution for privacy
- **Answer evaluation**: Semantic similarity scoring

### 📊 Performance Analysis
- **Automatic evaluation**: Compares model performance
- **Best answer selection**: Chooses highest-scoring responses
- **Detailed metrics**: Similarity scores and comparative analysis
- **Result export**: Saves evaluations and best answers

## 🚀 Quick Start

### Prerequisites

1. **Install Ollama**
   ```bash
   # Download from https://ollama.ai/
   ollama pull llama3.2:3b
   ollama pull llava:7b
   ```

2. **Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

### Basic Usage

1. **Place your patent PDF** in the project directory
2. **Create questions file** (`questions.txt`) with one question per line
3. **Run the pipeline**:
   ```python
   python main.py
   ```

### Example Questions (`questions.txt`)
```
What is the main invention described in this patent?
How does the system improve upon existing technology?
What are the key technical components?
Which figures show the system architecture?
What problem does this invention solve?
```

## 📁 Project Structure

```
GenAI - Final project/
├── main.py                 # Main RAG pipeline
├── questions.txt           # Input questions
├── answers.txt             # Best answers output
├── all_metadata.json       # Processed chunks metadata
├── evaluation_results.txt  # Detailed evaluation metrics
├── prompt_llama.txt        # LLaMA prompts log
├── prompt_llava.txt        # LLaVA prompts log
├── extracted_images/       # Extracted patent images
├── US6285999.pdf          # Sample patent document
├── US11960514.pdf         # Sample patent document
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## 🔧 Pipeline Steps

### Step 1: Document Chunking
```python
# Extract text and images from patent PDF
chunks = extract_text_and_images_from_patent("patent.pdf")
```

### Step 2: Vector Store Creation
```python
# Create embeddings and vector database
client, model = create_vector_store(chunks)
```

### Step 3: Question Processing
```python
# Load questions from file
questions = load_questions("questions.txt")
```

### Step 4: RAG Prompt Construction
```python
# Build context-aware prompts
rag_prompts = process_questions_with_rag(questions, chunks, client, model)
```

### Step 5: Answer Generation
```python
# Generate answers using LLaMA and LLaVA
answers = generate_answers(rag_prompts)
```

### Step 6: Evaluation & Selection
```python
# Evaluate and select best answers
evaluation_results = answers_eval(rag_prompts, answers)
```

## ⚙️ Configuration

### Model Settings
- **Text Model**: `llama3.2:3b` (configurable)
- **Vision Model**: `llava:7b` (configurable)
- **Embedding Model**: `all-MiniLM-L6-v2` (384 dimensions)
- **Vector Store**: Qdrant in-memory mode

### Performance Parameters
- **Top-k retrieval**: 3 text chunks
- **Max images**: 2 per question
- **Context limit**: 2000 bytes
- **Answer limit**: 300 characters

### OCR Settings
- **Default**: Disabled for faster processing
- **Enable**: Set `enable_ocr=True` for scanned documents
- **Language**: English (`en`)
- **Processing**: Gaussian blur + OTSU thresholding

## 📋 Requirements

### Core Dependencies
```txt
PyMuPDF>=1.23.0          # PDF processing
sentence-transformers     # Text embeddings
qdrant-client            # Vector database
scikit-learn             # Similarity metrics
easyocr                  # OCR capabilities
opencv-python            # Image processing
numpy                    # Numerical operations
Pillow                   # Image handling
```

### System Requirements
- **Python**: 3.8+
- **RAM**: 8GB+ recommended (for embeddings)
- **Storage**: 2GB+ for models
- **OS**: Windows/Linux/macOS
- **Ollama**: Latest version installed

## 🎮 Usage Examples

### Basic Patent Analysis
```python
# Analyze a single patent
python main.py
```

### Custom Questions
```python
# Create custom questions
with open("questions.txt", "w") as f:
    f.write("What is the technical innovation?\n")
    f.write("How does it work?\n")
    f.write("What are the advantages?\n")
```

### Enable OCR for Scanned Patents
```python
# Modify main.py
all_metadata = extract_text_and_images_from_patent(pdf_path, enable_ocr=True)
```

### Evaluation Only
```python
# Run just the evaluation
evaluation_results = answers_eval(rag_prompts, answers)
```

## 📊 Output Files

### `answers.txt`
Contains the best answers selected by similarity scoring:
```
=== BEST ANSWERS BASED ON SIMILARITY SCORES ===

Question 1: What is the main invention?
Best Answer (LLaVA - Similarity: 0.8234):
The patent describes a method for...
```

### `evaluation_results.txt`
Detailed performance metrics:
```
=== SEMANTIC SIMILARITY EVALUATION RESULTS ===

Question 1: What is the main invention?
LLaMA Similarity Score: 0.7234
LLaVA Similarity Score: 0.8234
```

### `all_metadata.json`
Processed document chunks:
```json
{
  "US6285999.pdf": {
    "chunks": [
      {
        "type": "text",
        "page": 1,
        "content": "Patent text content..."
      }
    ]
  }
}
```

## 🐛 Troubleshooting

### Common Issues

**Ollama not found**
```bash
# Check if Ollama is installed and running
ollama --version
ollama list
```

**Model not available**
```bash
# Pull required models
ollama pull llama3.2:3b
ollama pull llava:7b
```

**Memory issues**
- Reduce `max_context_bytes` in `construct_rag_prompt()`
- Process fewer chunks at once
- Use smaller embedding models

**OCR errors**
- Install system dependencies: `apt-get install ffmpeg libsm6 libxext6`
- Check image quality and language settings
- Disable OCR: `enable_ocr=False`

**PDF processing fails**
- Ensure PDF is not password-protected
- Check file permissions
- Verify PDF format compatibility

## 🔬 Advanced Usage

### Custom Embedding Models
```python
# Use different embedding model
client, model = create_vector_store(chunks, model_name="all-mpnet-base-v2")
```

### Batch Processing
```python
# Process multiple patents
pdf_files = ["patent1.pdf", "patent2.pdf", "patent3.pdf"]
for pdf_path in pdf_files:
    all_metadata = extract_text_and_images_from_patent(pdf_path)
    save_chunks_metadata(all_metadata)
```

### Custom Evaluation Metrics
```python
# Modify evaluate_single_answer() for custom scoring
def evaluate_single_answer(prompt, answer, model_name):
    # Add your custom evaluation logic
    return custom_score
```

## 📜 License

This project is provided as-is for educational and research purposes.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📞 Support

For issues and questions:
- Check the troubleshooting section
- Review error logs in console output
- Verify all dependencies are installed
- Ensure Ollama models are available

---

**Built with ❤️ for patent analysis and AI research**