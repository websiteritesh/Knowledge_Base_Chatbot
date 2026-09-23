"""
Basic tests for the Knowledge Base Chatbot API.
Run with: pytest -v      (from inside the backend folder)
"""
from fastapi.testclient import TestClient
from main import app, ADMIN_USERNAME

client = TestClient(app)


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
    """
    NOTE: replace 'your_real_password' below with your actual admin password
    before running this test (or it will fail, which is expected behavior).
    """
    response = client.post(
        "/login",
        data={"username": ADMIN_USERNAME, "password": "wordout48639"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_ask_with_valid_token_works():
    """Full flow: log in, get a token, then successfully ask a question."""
    login_response = client.post(
        "/login",
        data={"username": ADMIN_USERNAME, "password": "wordout48639"}
    )
    token = login_response.json()["access_token"]

    response = client.post(
        "/ask",
        json={"question": "What does TechCorp Solutions do?"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert "answer" in response.json()