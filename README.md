# Knowledge Base Chatbot

A production-style RAG (Retrieval-Augmented Generation) chatbot that answers questions from your own PDF documents — with real vector search, authentication, persistent history, and a fallback to general AI knowledge when your documents don't have the answer.

Built with FastAPI, PostgreSQL, ChromaDB, and Google Gemini.

## Features

- **Real vector-search RAG** — documents are chunked and embedded in ChromaDB, not just dumped as raw text
- **BM25 re-ranking** — retrieves a wide set of candidate chunks, then re-ranks them by keyword relevance for more accurate answers (hybrid search)
- **General-knowledge fallback** — if the answer isn't in your documents, the AI answers from general knowledge instead, clearly labeled so it's never mistaken for a document-sourced answer
- **JWT authentication** — login-protected API and UI; no one can query the chatbot without a valid token
- **Persistent chat history** — every question and answer is saved to a PostgreSQL database (Supabase)
- **Automatic retry logic** — AI API calls retry with exponential backoff if the provider is temporarily overloaded
- **Dockerized** — runs identically anywhere via Docker Compose
- **Tested** — pytest suite covering authentication, authorization, and the core RAG flow
- **CI** — GitHub Actions runs the full test suite automatically on every push

## Tech stack

| Layer | Tools |
|---|---|
| Backend | Python, FastAPI, Uvicorn |
| AI | Google Gemini API (`gemini-3.6-flash`) |
| Retrieval | ChromaDB (vector search), rank-bm25 (re-ranking) |
| Database | PostgreSQL via Supabase, SQLAlchemy |
| Auth | JWT (python-jose), bcrypt |
| Testing | pytest, httpx |
| Deployment | Docker, Docker Compose |
| CI/CD | GitHub Actions |

## Project structure

```
backend/
├── main.py              # FastAPI app: RAG, auth, chat history
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── frontend/
│   └── index.html        # Login screen + chat UI
├── tests/
│   └── test_main.py
├── documents/            # Uploaded PDFs (not tracked in git)
└── .github/workflows/
    └── ci.yml
```

## Running locally

1. Create `backend/.env` with:
   ```
   GEMINI_API_KEY=your_gemini_api_key
   DATABASE_URL=your_postgres_connection_string
   SECRET_KEY=a_random_secret_string
   ADMIN_USERNAME=your_chosen_username
   ADMIN_PASSWORD_HASH_B64=base64_encoded_bcrypt_hash
   ```
2. Install dependencies:
   ```
   pip install -r backend/requirements.txt
   ```
3. Run:
   ```
   uvicorn main:app --reload
   ```
4. Open `http://127.0.0.1:8000/app`, log in, upload a PDF, and start asking questions.

## Running with Docker

```
cd backend
docker compose up --build
```

## Running tests

```
cd backend
pytest -v
```

## How it works

1. A PDF is uploaded and split into overlapping text chunks
2. Chunks are embedded and stored in ChromaDB
3. On a question: the top 10 semantically similar chunks are retrieved, then re-ranked with BM25 keyword scoring down to the best 4
4. Those chunks are sent to Gemini as context, with instructions to answer only from them
5. If the documents don't contain the answer, a second AI call answers from general knowledge instead — clearly labeled as such
6. The question and answer are saved to PostgreSQL



