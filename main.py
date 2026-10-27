import shutil
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from langgraph.types import Command

from nyaya_graph import nyaya_app, reload_retrievers

app = FastAPI(title="Nyaya.AI")

# Mount static directory for HTML, CSS, JS
app.mount("/static", StaticFiles(directory="static"), name="static")

class CaseRequest(BaseModel):
    thread_id: str
    case_category: str
    raw_query: str

class HITLDecisionRequest(BaseModel):
    thread_id: str
    decision: str  # "approve" or custom feedback text

@app.get("/")
async def serve_ui():
    return FileResponse("static/index.html")

@app.post("/api/analyze")
async def analyze_case(req: CaseRequest):
    """Starts the LangGraph workflow until it hits the Human-in-the-Loop interrupt()."""
    config = {"configurable": {"thread_id": req.thread_id}, "recursion_limit": 25}
    
    initial_state = {
        "case_category": req.case_category,
        "raw_query": req.raw_query,
        "messages": [],
        "query_type": "",
        "retrieved_context": "",
        "legal_audit": {},
        "draft": "",
        "review_feedback": "",
        "is_approved": False,
        "attempt": 0,
        "final_output": ""
    }

    try:
        result = nyaya_app.invoke(initial_state, config)
        is_interrupted = "__interrupt__" in result
        interrupt_payload = result["__interrupt__"][0].value if is_interrupted else None

        return {
            "status": "paused_for_human" if is_interrupted else "completed",
            "thread_id": req.thread_id,
            "query_type": result.get("query_type", ""),
            "retrieved_context": result.get("retrieved_context", ""),
            "legal_audit": result.get("legal_audit", {}),
            "draft": result.get("draft", ""),
            "review_feedback": result.get("review_feedback", ""),
            "attempt": result.get("attempt", 1),
            "interrupt_data": interrupt_payload,
            "final_output": result.get("final_output", "")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hitl-decision")
async def submit_hitl_decision(req: HITLDecisionRequest):
    """Resumes the paused LangGraph thread using Command(resume=...) as taught in the video."""
    config = {"configurable": {"thread_id": req.thread_id}, "recursion_limit": 25}

    try:
        result = nyaya_app.invoke(Command(resume=req.decision), config)
        is_interrupted = "__interrupt__" in result
        interrupt_payload = result["__interrupt__"][0].value if is_interrupted else None

        return {
            "status": "paused_for_human" if is_interrupted else "completed",
            "thread_id": req.thread_id,
            "query_type": result.get("query_type", ""),
            "legal_audit": result.get("legal_audit", {}),
            "draft": result.get("draft", ""),
            "review_feedback": result.get("review_feedback", ""),
            "attempt": result.get("attempt", 1),
            "interrupt_data": interrupt_payload,
            "final_output": result.get("final_output", "")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload-pdf")
async def upload_legal_pdf(doc_type: str, file: UploadFile = File(...)):
    """Allows uploading custom BNS or Procedure PDFs to update FAISS Vector Store."""
    filename = "bns_handbook.pdf" if doc_type == "statutes" else "legal_procedures.pdf"
    with open(filename, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    reload_retrievers()
    return {"message": f"{filename} successfully indexed into FAISS Vector Store!"}