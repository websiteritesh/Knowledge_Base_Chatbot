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



load_dotenv()
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

app = FastAPI(title="Knowledge Base Chatbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.mount("/static", StaticFiles(directory="../frontend"), name="static")

@app.get("/app")
def serve_frontend():
    return FileResponse("../frontend/index.html")

# Store all document text in memory
knowledge_base = ""
pdf_count = 0

class QuestionRequest(BaseModel):
    question: str

def load_all_pdfs(folder: str):
    global knowledge_base, pdf_count
    all_text = ""
    files = [f for f in os.listdir(folder) if f.endswith(".pdf")]
    pdf_count = len(files)

    for filename in files:
        path = os.path.join(folder, filename)
        reader = PdfReader(path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        all_text += f"\n\n=== Document: {filename} ===\n\n{text}"

    knowledge_base = all_text
    return pdf_count

@app.on_event("startup")
async def startup():
    folder = "documents"
    if os.path.exists(folder):
        count = load_all_pdfs(folder)
        print(f"Loaded {count} PDF files into knowledge base")

@app.get("/")
def home():
    return {
        "status": "running",
        "knowledge_base_ready": knowledge_base != "",
        "pdf_count": pdf_count
    }

@app.get("/status")
def status():
    return {
        "knowledge_base_ready": knowledge_base != "",
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

@app.post("/ask")
def ask(request: QuestionRequest):
    if not knowledge_base:
        return {"error": "No documents loaded. Please upload a PDF first."}

    prompt = f"""You are a helpful knowledge base assistant.
Answer the question using ONLY the documents below.
If the answer is not in the documents say: I don't have information about that in the knowledge base.
Be clear and professional.

Documents:
{knowledge_base[:3000]}

Question: {request.question}"""

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt
    )

    return {
        "question": request.question,
        "answer": response.text,
        "sources_found": pdf_count
    }