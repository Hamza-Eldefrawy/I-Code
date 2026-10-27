import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request, UploadFile
from pydantic import BaseModel

from src.code_runner import run_code
from src.llm import LLM
from src.orchestrator import Orchestrator
from src.retriever import Retriever
from src.sessions import SessionStore
from src.sql import SQLiteDB, format_table
from src.voice import Voice

from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    llm = LLM()
    retriever = Retriever()
    app.state.voice = Voice()
    app.state.sessions = SessionStore(llm, retriever)
    yield


app = FastAPI(title="I-Code API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- helpers ----------

def get_session(request: Request, x_session_id: str = Header(...)) -> Orchestrator:
    orch = request.app.state.sessions.get(x_session_id)
    if orch is None:
        raise HTTPException(404, "Unknown session. POST /sessions first.")
    return orch


class TextIn(BaseModel):
    text: str


class FeedbackIn(BaseModel):
    request: str    # the original question
    solution: str   # the code that answers it


class SqlQuestion(BaseModel):
    question: str


class SqlRaw(BaseModel):
    sql: str


# ---------- sessions ----------

@app.post("/sessions")
def create_session(request: Request):
    return {"session_id": request.app.state.sessions.create()}


@app.delete("/sessions/{sid}")
def delete_session(sid: str, request: Request):
    request.app.state.sessions.delete(sid)
    return {"deleted": sid}


# ---------- voice ----------

@app.post("/voice/start")
def voice_start(request: Request):
    request.app.state.voice.start_recording()
    return {"status": "recording"}


@app.post("/voice/stop")
def voice_stop(request: Request):
    audio = request.app.state.voice.stop_recording()
    transcript = request.app.state.voice.transcribe(audio)
    return {"transcript": transcript}


@app.post("/voice/transcribe")
async def voice_transcribe(file: UploadFile, request: Request):
    with tempfile.NamedTemporaryFile(suffix=Path(file.filename).suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)
    transcript = request.app.state.voice.transcribe(tmp_path)
    tmp_path.unlink(missing_ok=True)
    return {"transcript": transcript}


# ---------- analysis ----------

@app.post("/analyze")
def analyze(body: TextIn, orch: Orchestrator = Depends(get_session)):
    return {"intent": orch.llm.classify(body.text, context=orch.memory.last_exchange())}


# ---------- SQL ----------

@app.post("/sql/upload")
async def sql_upload(file: UploadFile, orch: Orchestrator = Depends(get_session)):
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)
    if not hasattr(orch, "db"):
        orch.db = SQLiteDB()
    summary = orch.db.load_csv(str(tmp_path), table=Path(file.filename).stem)
    tmp_path.unlink(missing_ok=True)
    return summary


@app.post("/sql/query")
def sql_query(body: SqlQuestion, orch: Orchestrator = Depends(get_session)):
    if not hasattr(orch, "db") or not orch.db.is_loaded():
        raise HTTPException(400, "No CSV loaded. POST /sql/upload first.")
    sql = orch.llm.text2sql(body.question, orch.db.schema())
    return {"sql": sql}


@app.post("/sql/execute")
def sql_execute(body: SqlRaw, orch: Orchestrator = Depends(get_session)):
    if not hasattr(orch, "db") or not orch.db.is_loaded():
        raise HTTPException(400, "No CSV loaded. POST /sql/upload first.")
    try:
        result = orch.db.execute(body.sql)
    except Exception as e:
        raise HTTPException(400, f"SQL error: {e}")
    return {"table": format_table(result), "raw": result}


# ---------- coding ----------

@app.post("/explain")
def explain(body: TextIn, orch: Orchestrator = Depends(get_session)):
    return {"answer": orch.explain(body.text)}


@app.post("/generate")
def generate(body: TextIn, orch: Orchestrator = Depends(get_session)):
    answer = orch.handle(body.text)
    return {"answer": answer, "not_found": orch.awaiting_solution}


@app.post("/feedback")
def feedback(body: FeedbackIn, orch: Orchestrator = Depends(get_session)):
    doc_id = orch.ingest_solution(body.request, body.solution)
    orch.awaiting_solution = False
    orch.pending_request = None
    return {"stored": doc_id}


# ---------- execution ----------

@app.post("/run")
def run(body: TextIn):
    return run_code(body.text)
