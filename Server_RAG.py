from fastapi import FastAPI, Body, HTTPException
import Patent_RAG

app = FastAPI()

@app.post("/process_patent")
def process_patent(pdf_path: str = Body(..., embed=True)):
    try:
        # Call main function expecting no exception
        chunks, client, model, questions, rag_prompts, answers, evaluation_results = Patent_RAG.main(pdf_path)
        return {"status": "success",
                "status_code": 200,
                "message": "Patent processed successfully",
                "data": {
                    "chunks": chunks,
                    "client": client,
                    "model": model,
                    "questions": questions,
                    "rag_prompts": rag_prompts,
                    "answers": answers,
                    "evaluation_results": evaluation_results
                }
                }
    except Exception as e:
        # Return error response
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail={"status": "error"})

    
@app.get("/health")
async def health_check():
    return {"status": "healthy"}