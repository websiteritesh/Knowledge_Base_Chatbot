"""
Basic tests for the Knowledge Base Chatbot API.
Run with: pytest -v      (from inside the backend folder)

The real admin password is never written in this file — it's read from an
environment variable (TEST_ADMIN_PASSWORD) so it's never committed to Git.
Set it in your .env file, or as a GitHub Actions secret for CI.
"""
import os
from fastapi.testclient import TestClient
from main import app, ADMIN_USERNAME

client = TestClient(app)
TEST_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD")


def test_status_endpoint_is_reachable():
    """The /status endpoint should always respond, even with no documents loaded."""
    response = client.get("/status")
    assert response.status_code == 200
    assert "knowledge_base_ready" in response.json()


def test_ask_without_token_is_blocked():
    """Anyone without a valid JWT should be rejected — this proves our auth actually works."""
    response = client.post("/ask", json={"question": "What is this document about?"})
    assert response.status_code == 401


def test_login_with_wrong_password_fails():
    """A wrong password should never succeed."""
    response = client.post(
        "/login",
        data={"username": ADMIN_USERNAME, "password": "definitely_the_wrong_password"}
    )
    assert response.status_code == 401


def test_login_with_correct_password_returns_a_token():
    response = client.post(
        "/login",
        data={"username": ADMIN_USERNAME, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_ask_with_valid_token_works():
    """
    Full flow: log in, get a token, then call /ask successfully.
    This checks that authentication and the endpoint itself work correctly —
    it doesn't assume any specific PDF is loaded, since a fresh environment
    (like CI) starts with no documents uploaded.
    """
    login_response = client.post(
        "/login",
        data={"username": ADMIN_USERNAME, "password": TEST_PASSWORD}
    )
    token = login_response.json()["access_token"]

    response = client.post(
        "/ask",
        json={"question": "What does TechCorp Solutions do?"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    # Either a real answer (if documents are loaded) or the expected
    # "no documents" message (in a fresh environment) — both are valid,
    # correct behavior. What matters here is that auth + the endpoint work.
    body = response.json()
    assert "answer" in body or "error" in body