"""
AI Evaluation script for the Knowledge Base Chatbot.

Concept: instead of trusting the chatbot "feels" accurate, we ask it a fixed
set of questions we already know the correct answer to (a "golden set"),
then check whether each answer actually contains the expected key facts.

Run with: python evaluate.py
(make sure your server is running first: uvicorn main:app --reload,
 and that TechCorp_FAQ.pdf is uploaded/loaded)
"""
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://127.0.0.1:8000"

# The golden set: each question paired with key facts that MUST appear
# in a correct answer. We don't need an exact match — just proof the
# right information came through.
GOLDEN_SET = [
    {
        "question": "Who is the CEO of TechCorp Solutions?",
        "must_contain": ["Priya Sharma"],
    },
    {
        "question": "How much does the AutoChat basic plan cost?",
        "must_contain": ["5,000", "5000"],  # accept either format
    },
    {
        "question": "What is the refund policy?",
        "must_contain": ["30-day", "30 day"],
    },
    {
        "question": "Does TechCorp offer a free trial?",
        "must_contain": ["14-day", "14 day"],
    },
    {
        "question": "Where is TechCorp headquartered?",
        "must_contain": ["Bangalore"],
    },
    {
        "question": "What is the capital of France?",  # deliberately NOT in the PDF
        "must_contain": ["Paris"],  # should trigger the general-knowledge fallback
    },
]


def get_token():
    response = requests.post(
        f"{BASE_URL}/login",
        data={
            "username": os.getenv("ADMIN_USERNAME"),
            "password": os.getenv("TEST_ADMIN_PASSWORD"),
        },
    )
    return response.json()["access_token"]


def run_evaluation():
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}

    passed = 0
    total = len(GOLDEN_SET)

    print(f"Running evaluation on {total} questions...\n")

    for i, case in enumerate(GOLDEN_SET, 1):
        response = requests.post(
            f"{BASE_URL}/ask",
            json={"question": case["question"]},
            headers=headers,
        )
        full_response = response.json()
        answer = full_response.get("answer", "")

        # Pass if ANY of the acceptable phrasings appear in the answer
        found = any(phrase.lower() in answer.lower() for phrase in case["must_contain"])

        status = "PASS" if found else "FAIL"
        if found:
            passed += 1

        print(f"[{status}] Q{i}: {case['question']}")
        if not found:
            print(f"       Expected one of: {case['must_contain']}")
            print(f"       Full response: {full_response}")
        print()

        time.sleep(2)  # small pause between requests to avoid API rate limits

    accuracy = (passed / total) * 100
    print(f"{'=' * 50}")
    print(f"RESULT: {passed}/{total} passed ({accuracy:.1f}% accuracy)")


if __name__ == "__main__":
    run_evaluation()