from fastapi import FastAPI, Body
import Patent_RAG

app = FastAPI()

@app.post("/process_patent")
async def process_patent(pdf_path: str = Body(..., embed=True)):
    return await Patent_RAG.main(pdf_path)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}