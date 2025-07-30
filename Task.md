# ✅ Programming Assignment: Patent-Based Q&A Using RAG and Multimodal LLMs

## 🎯 Objective  
Build a Python-based pipeline that analyzes a real-world patent document (including both text and images) and answers questions using Retrieval-Augmented Generation (RAG) powered by **LLaVA** and **LLaMA** via **Ollama**.

---

## 📥 Input: Patent Document  
Manually download a patent PDF from [Google Patents](https://patents.google.com/).  
Example: [US11960514B1](https://patents.google.com/patent/US11960514B1)  
Save the file as `patent.pdf` in your working directory. A sample extract is included in the assignment folder.

---

## 📄 Step 1: Chunking the Patent  

- **Text Extraction:**  
  Use OCR and PDF parsing tools to extract the text content of each page.

- **Image Extraction:**  
  Extract all figures and diagrams, saving them as image files.

- **Metadata Format (for each chunk):**
  ```python
  {
      "type": "text" or "image",
      "page": <page_number>,
      "content": <text or image file path>
  }
  ```

---

## 📦 Step 2: Vector Store  

- Use a `SentenceTransformer` model to encode all **text chunks**.  
- Store the resulting vectors in an **in-memory Qdrant** vector database to enable semantic search.

---

## ❓ Step 3: Question Input  

Read a list of questions from `questions.txt`. Each line in the file should contain a single question.

---

## 🧠 Step 4: Prompt Construction (RAG)

For each question:

1. Retrieve the **top-k relevant text chunks** using Qdrant.
2. Select up to **2 nearby image chunks** from the same or adjacent pages.
3. Construct a prompt in the following structure:
   ```
   Question: <question text>

   Context:
   <retrieved text chunks — limited to 2000 bytes>

   Images:
   <image1 path>, <image2 path>
   ```

You must ensure all constraints (text length, number of images) are enforced.

---

## 🤖 Step 5: Answer Generation  

- Use **LLaVA** for interpreting images and **LLaMA** for generating textual answers via `ollama`.  
- Answers must be limited to **300 characters**.  
- Ensure that answers are based **only on retrieved chunks** — no hallucinations.

---

## 📤 Step 6: Output Format  

Write answers to a file named `answers.txt` using the format:

```
Question <number>: <question text>
<single-line answer>
```

---

## 💡 Hints  

- Use `easyocr` for OCR tasks.  
- Use `SentenceTransformer` for text embeddings.  
- Use `subprocess.Popen(...)` to call `ollama` from Python.  
- Start with a small test patent.  
- All files are assumed to reside in the current working directory (`pwd`).

---

## 🧩 Development Hint

This is a complex task. It is highly recommended to **implement and test the solution step by step**, validating each stage (e.g., text extraction, vector storage, retrieval, image handling, LLM invocation) before combining them into the full pipeline.

---

## 📦 Submission Checklist  

Your submission must include:

- `questions.txt` — input file  
- `answers` — output file  
- All image files used  
- A Jupyter notebook with the complete code  
- A transcript of your LLM interactions during development  

> **Collaboration Policy:** You may discuss general ideas with others, but all submitted code and answers must be your own.

---

## 🧪 Evaluation Criteria

- ✅ **Correctness**: Answers will be evaluated against a set of 100 questions using one of five provided patent PDFs.
- ✅ **Development Sample**: A sample of 20 development questions will be provided in advance.
- ✅ **Completeness**: Your code must produce answers for all 100 questions.
- ✅ **Code Quality**: Assessed by an LLM using a structured rubric.
- ✅ **Performance**: Total runtime (loading, retrieval, answering) will be measured.

---

## ⚠️ Deductions

| Condition                                             | Penalty   |
|------------------------------------------------------|-----------|
| Use of unavailable libraries                         | -30       |
| Runtime > 20 minutes                                 | -20       |
| Runtime > 30 minutes                                 | -100      |
| Prompt exceeds 2000 bytes or uses >2 images          | -20       |
| Installing anything in the environment               | -100      |
| Code quality score < 5 (out of 5)                    | `-20 × (1 - score/5)` |

---

## 🧪 Oral Assessment

Following submission, each student will participate in a **10–15 minute individual oral assessment via Zoom**. You will be asked to:

- Describe the structure and flow of your pipeline  
- Explain the purpose of each function  
- Clarify the key parameters used  
- Demonstrate an understanding of the *role* of each algorithm/method (you are **not** expected to explain their internals)

> **For example**: You do *not* need to explain how cosine similarity or SentenceTransformer works internally.

---

### 🎯 Oral Assessment Grading

- Graded on a scale of **1 to 10**  
  - **10** = full understanding  
  - **1** = minimal or no understanding

### ⚠️ Oral Assessment Penalty

```
Additional deduction = (10 - Oral Score) × 3
```

**Examples:**
- Score 10 → No penalty  
- Score 7 → -9 points  
- Score 1 → -27 points  

---

## 🏁 Final Score Calculation

$$
\text{Final Score} = \min \left(100,\ \frac{\text{Your correct answers}}{\text{Gadi’s correct answers}} \times 100 \right) - \text{Total Deductions}
$$



---

## 🛠️ Libraries Used in Reference Implementation

In my reference solution, I used the following Python libraries. **You are not required to use the same libraries**, and you are free to implement equivalent functionality with tools of your choice (As long as you don't need to install anything in the environment).

```python
import os
import subprocess
import fitz  # PyMuPDF
import json
from sentence_transformers import SentenceTransformer
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from sklearn.metrics.pairwise import cosine_similarity
import tempfile
from PIL import Image
import io
import easyocr
from langchain.text_splitter import (
    CharacterTextSplitter,
    NLTKTextSplitter,
    SpacyTextSplitter,
    RecursiveCharacterTextSplitter
)
from IPython.display import Image, display
```

These libraries were selected for convenience, community support, and integration with Ollama and Qdrant, but **feel free to adapt your own stack** (As long as you don't need to install anything in the environment).

---

# ✅ LLM Prompt: Python Code Quality Review

Please review the following Python code and evaluate it across the criteria below. For each, assign a score from **1 (poor)** to **5 (excellent)** and briefly explain your rating. If a score is less than 5, provide a specific improvement suggestion.

### Evaluation Criteria:

1. **Code Structure & Organization** – Is the code modular and well-organized?
2. **Naming Conventions** – Are variable and function names clear and consistent?
3. **Documentation & Comments** – Are docstrings and comments helpful and correctly placed?
4. **Error Handling** – Are errors anticipated and handled gracefully?
5. **Code Clarity & Readability** – Is the code clean and easy to read?
6. **Reusability & Modularity** – Are components reusable and logically separated?
7. **Testing & Validation** – Are there tests, assertions, or validation mechanisms?

### Final Score:
- Compute the average score.
- Round to the nearest **whole or half point**.
- Provide:
  - A brief summary of **strengths**
  - Suggestions for **improvement**

# ✅ Prompt for Evaluating the Quality of the Answers

You are an expert evaluator. Your task is to assess the quality of answers to technical questions based **only on the content of the provided patent PDF**. Do not rely on external knowledge or make assumptions beyond what is written in the document.

---

## 📄 Input

You will receive:

1. A **PDF file** containing a patent.
2. A list of answers in the following format:
   ```
   Question <number>: <question text>
   <single-line answer>
   ```

---

## 🎯 Scoring Criteria

For each question, assign a **base score** as follows:

| Condition                  | Base Score |
|---------------------------|------------|
| Correct and complete      | 10         |
| Correct but incomplete    | 7          |
| Incorrect                 | 1          |
| Hallucinated content      | 1          |

### ⚠️ Adjustment

- If the answer exceeds **300 characters**, subtract **1 point** from the base score.

---

## 📝 Output Format

For each question, return the following:

```
Question <number>: <question text>
Score: <final score>/10
Explanation: <brief and specific explanation — if score < 10>

- If incomplete: list what was missing
- If incorrect: explain what was wrong and what the correct answer should be
- If hallucinated: specify which part of the answer was not supported by the patent
- If too long: indicate actual character count and apply the deduction
```

At the end of the evaluation, print:

```
Average Score: <value out of 10>
```

---

## ❌ Invalid Input Handling

If the input format is invalid (e.g., malformed lines, mismatched questions and answers), return:

```
Final Score: 0
Reason: Invalid file format.
```

---

## 🧠 Guidelines for the Evaluator

- A **hallucination** refers to content not supported by the patent.
- A **correct but incomplete** answer omits key details found in the text.
- Do **not** guess or assume beyond what the patent clearly states.
- Count characters carefully — answers must be ≤ 300 characters to avoid a penalty.

- 
## ⚠️ Disclaimer

The evaluation prompts provided for answer quality and code review are guidelines and may be **adapted or refined** by the course staff if needed. 
message.txt
10 KB