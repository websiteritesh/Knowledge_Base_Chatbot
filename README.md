# Knowledge Base Chatbot

An AI-powered chatbot that answers questions from your PDF documents.
Built with FastAPI and Google Gemini AI.

## What it does
- Upload any PDF document through the browser
- Ask questions in plain English
- AI answers using only your document content
- Says "I don't have information about that" for out-of-scope questions

## Tools used
- Python
- FastAPI
- Google Gemini API (gemini-3.6-flash)
- pypdf
- Uvicorn

## How to run
1. Add your Google API key to .env file
2. Run: uvicorn main:app --reload
3. Open: http://127.0.0.1:8000/app
4. Upload a PDF and start asking questions