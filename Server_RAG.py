from fastapi import FastAPI, Body, HTTPException
import Patent_RAG

app = FastAPI()

@app.post("/process_patent")
def process_patent(pdf_path: str = Body(..., embed=True)): # 3 dots of Body made the arg mandatory use None for optional.
    """
        Process a patent document and return the results in a structured format.
        Args:
            pdf_path: The path to the patent document.
        Returns:
            A dictionary containing the results of the patent processing.
    """
    try:
        # Call main function expecting no exception
        Patent_RAG.main(pdf_path)
        return {"status": "success",
                "status_code": 200,
                "message": "Patent processed successfully"
                }
    except Exception as e:
        # Return error response
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail={"status": "error"})

    
@app.get("/health")
async def health_check():
    return {"status": "healthy"}