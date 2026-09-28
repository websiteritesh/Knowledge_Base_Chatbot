from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import os
import shutil
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from pypdf import PdfReader
from google import genai
import chromadb



load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# --- Retry helper ---
# The AI provider's servers can be temporarily overloaded (503 errors).
# This retries the call a few times with increasing wait time before giving up.
import time

def call_ai_with_retry(prompt_text, max_retries=3):
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt_text
            )
        except Exception as e:
            if attempt == max_retries - 1:
                raise  # out of retries, let the real error surface
            wait_time = 2 ** attempt  # 1s, then 2s, then 4s
            print(f"AI call failed ({e}), retrying in {wait_time}s...")
            time.sleep(wait_time)

# --- Database setup ---
from sqlalchemy import create_engine, text
db_engine = create_engine(os.getenv("DATABASE_URL"))

def init_db():
    with db_engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id SERIAL PRIMARY KEY,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.commit()

# --- Vector database setup (ChromaDB) ---
chroma_client = chromadb.PersistentClient(path="chroma_db")
collection = chroma_client.get_or_create_collection(name="documents")

# --- Re-ranker setup (Advanced RAG) ---
# Using BM25 (keyword relevance scoring) instead of a neural cross-encoder —
# no heavy ML dependencies, works everywhere, and is a real hybrid-search technique.
from rank_bm25 import BM25Okapi

# --- Agent setup (LangGraph) ---
# This turns retrieval from a single fixed pass into a small loop: retrieve,
# generate an answer, and if the documents didn't have it, rewrite the
# question once and try again before giving up — a real agentic decision.
from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class AgentState(TypedDict):
    original_question: str
    current_query: str
    attempts: int
    chunks: List[str]
    answer: str

NOT_FOUND_MESSAGE = "I don't have information about that in the knowledge base"

def retrieve_node(state: AgentState) -> AgentState:
    """Vector search + BM25 re-rank, using whatever query is current
    (the original question on attempt 1, a rewritten version after that)."""
    results = collection.query(query_texts=[state["current_query"]], n_results=10)
    candidates = results["documents"][0]

    if not candidates:
        state["chunks"] = []
        return state

    tokenized = [c.lower().split() for c in candidates]
    bm25 = BM25Okapi(tokenized)
    scores = bm25.get_scores(state["current_query"].lower().split())
    ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
    state["chunks"] = [chunk for score, chunk in ranked[:4]]
    return state

def generate_node(state: AgentState) -> AgentState:
    """Answer using only the retrieved chunks, based on the ORIGINAL question
    (we search with the rewritten query, but always answer the real question asked)."""
    context = "\n\n".join(state["chunks"])
    prompt = f"""You are a helpful knowledge base assistant.
Answer the question using ONLY the documents below.
If the answer is not in the documents say: {NOT_FOUND_MESSAGE}
Be clear and professional.

Documents:
{context}

Question: {state['original_question']}"""

    response = call_ai_with_retry(prompt)
    state["answer"] = response.text
    return state

def rewrite_query_node(state: AgentState) -> AgentState:
    """The first search didn't find a good answer. Ask the AI to rewrite the
    question as a better search query — different phrasing, synonyms, or a
    more specific term — then we'll search again with that instead."""
    state["attempts"] += 1
    print(f"[AGENT] No good answer found. Rewriting question: '{state['original_question']}'")
    rewrite_prompt = f"""A document search for this question found nothing useful:
"{state['original_question']}"

Rewrite it as a short, alternative search query using different wording or
synonyms that might match the document's phrasing better. Respond with ONLY
the rewritten query, nothing else."""

    response = call_ai_with_retry(rewrite_prompt)
    state["current_query"] = response.text.strip()
    return state

def should_retry(state: AgentState) -> str:
    """The decision point: did we find a real answer, or should the agent
    try once more with a rewritten query before giving up?"""
    not_found = NOT_FOUND_MESSAGE in state["answer"]
    if not_found and state["attempts"] < 1:  # allow exactly one retry
        return "rewrite"
    return "end"

# Wire the nodes into a graph: retrieve -> generate -> (retry or stop)
_agent_graph = StateGraph(AgentState)
_agent_graph.add_node("retrieve", retrieve_node)
_agent_graph.add_node("generate", generate_node)
_agent_graph.add_node("rewrite", rewrite_query_node)
_agent_graph.set_entry_point("retrieve")
_agent_graph.add_edge("retrieve", "generate")
_agent_graph.add_conditional_edges("generate", should_retry, {"rewrite": "rewrite", "end": END})
_agent_graph.add_edge("rewrite", "retrieve")
rag_agent = _agent_graph.compile()

# --- Authentication setup (JWT) ---
import bcrypt
from jose import jwt, JWTError
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
import base64

# Stored as Base64 in .env to avoid Docker Compose mangling the $ characters
# that are a normal part of bcrypt hash format.
_hash_b64 = os.getenv("ADMIN_PASSWORD_HASH_B64")
ADMIN_PASSWORD_HASH = base64.b64decode(_hash_b64).decode() if _hash_b64 else None

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def create_access_token(username: str):
    expire = datetime.utcnow() + timedelta(hours=8)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["sub"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token, please log in again")

class LoginRequest(BaseModel):
    username: str
    password: str

app = FastAPI(title="Knowledge Base Chatbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/app")
def serve_frontend():
    return FileResponse("frontend/index.html")

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    correct_username = form_data.username == ADMIN_USERNAME
    correct_password = bcrypt.checkpw(form_data.password.encode(), ADMIN_PASSWORD_HASH.encode())

    if not (correct_username and correct_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    token = create_access_token(form_data.username)
    return {"access_token": token, "token_type": "bearer"}

pdf_count = 0

class QuestionRequest(BaseModel):
    question: str

def chunk_text(text_str, chunk_size=800, overlap=100):
    """Splits long text into overlapping pieces so each piece fits nicely
    into a search + AI prompt, and no sentence gets cut in half."""
    chunks = []
    start = 0
    while start < len(text_str):
        end = start + chunk_size
        chunks.append(text_str[start:end])
        start = end - overlap
    return chunks

def load_all_pdfs(folder: str):
    global pdf_count
    files = [f for f in os.listdir(folder) if f.endswith(".pdf")]
    pdf_count = len(files)

    # clear old chunks first so re-uploading doesn't create duplicates
    existing = collection.get()["ids"]
    if existing:
        collection.delete(ids=existing)

    chunk_id = 0
    for filename in files:
        path = os.path.join(folder, filename)
        reader = PdfReader(path)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"

        for chunk in chunk_text(full_text):
            if chunk.strip():
                collection.add(
                    documents=[chunk],
                    metadatas=[{"source": filename}],
                    ids=[f"chunk_{chunk_id}"]
                )
                chunk_id += 1

    return pdf_count

@app.on_event("startup")
async def startup():
    init_db()
    print("Database ready")

    folder = "documents"
    if os.path.exists(folder):
        count = load_all_pdfs(folder)
        print(f"Loaded {count} PDF files into knowledge base")

@app.get("/")
def home():
    return {
        "status": "running",
        "knowledge_base_ready": collection.count() > 0,
        "pdf_count": pdf_count
    }

@app.get("/status")
def status():
    return {
        "knowledge_base_ready": collection.count() > 0,
        "pdf_count": pdf_count
    }

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        return {"error": "Only PDF files allowed"}

    path = f"documents/{file.filename}"
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    count = load_all_pdfs("documents")

    return {
        "message": f"{file.filename} uploaded successfully",
        "pdf_count": count
    }

@app.get("/history")
def get_history():
    with db_engine.connect() as conn:
        rows = conn.execute(text("SELECT id, question, answer, created_at FROM chat_history ORDER BY created_at DESC"))
        return [dict(row._mapping) for row in rows]

@app.post("/ask")
def ask(request: QuestionRequest, current_user: str = Depends(verify_token)):
    if collection.count() == 0:
        return {"error": "No documents loaded. Please upload a PDF first."}

    try:
        result = rag_agent.invoke({
            "original_question": request.question,
            "current_query": request.question,
            "attempts": 0,
            "chunks": [],
            "answer": "",
        })
    except Exception:
        return {"error": "The AI service is temporarily unavailable. Please try again in a minute."}

    answer_text = result["answer"]
    source = "documents"

    # Fallback: if even after the agent's retry the documents didn't have the
    # answer, let the AI answer from its own general knowledge instead —
    # but clearly label it as such
    if NOT_FOUND_MESSAGE in answer_text:
        general_prompt = f"""You are a helpful, knowledgeable AI assistant.
Answer the following question naturally and helpfully, the way you'd answer in a normal conversation.
Give enough context and detail to actually be useful — don't just state a bare fact if more explanation would help.

Question: {request.question}"""

        try:
            general_response = call_ai_with_retry(general_prompt)
            answer_text = general_response.text
            source = "general_knowledge"
        except Exception:
            pass  # keep the original "I don't have information" answer if this also fails

    # Save this Q&A into the database so it's remembered permanently
    with db_engine.connect() as conn:
        conn.execute(
            text("INSERT INTO chat_history (question, answer) VALUES (:q, :a)"),
            {"q": request.question, "a": answer_text}
        )
        conn.commit()

    return {
        "question": request.question,
        "answer": answer_text,
        "source": source,
        "attempts": result["attempts"] + 1,
        "sources_found": len(result["chunks"])
    }