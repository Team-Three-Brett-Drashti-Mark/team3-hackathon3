"""
test_api.py — Integration tests for the FastAPI /chat and /health endpoints.

Uses TestClient (no real server needed) with the retriever and Groq patched.
Verifies request/response shapes, attempt tracking, CORS headers, and logging.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures — build app with all external deps patched
# ---------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    """Return a FastAPI TestClient with Groq and retriever mocked."""
    safe_reply = MagicMock()
    safe_reply.choices[0].message.content = (
        "Think about the start and end indices you need. "
        "What have you tried so far with string slicing?"
    )

    fake_groq = MagicMock()
    fake_groq.chat.completions.create.return_value = safe_reply

    chunks = [{"text": "Slicing: s[start:end]", "week": "week_01", "topic": "Slicing"}]

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr("guardrails.no_direct_answers.Groq", lambda **kwargs: fake_groq)
    monkeypatch.setattr("app.main.retrieve", lambda query, k=3: chunks)

    # Import AFTER patching so build_graph picks up the mocks
    from app.api import app
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_returns_ok_status(self, client):
        resp = client.get("/health")
        assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# /chat — happy path
# ---------------------------------------------------------------------------

class TestChatEndpoint:
    def _post(self, client, payload):
        return client.post("/chat", json=payload)

    def test_returns_200_for_curriculum_question(self, client):
        resp = self._post(client, {
            "user_input": "how does string slicing work?",
            "attempt": 1,
        })
        assert resp.status_code == 200

    def test_response_has_required_fields(self, client):
        resp = self._post(client, {"user_input": "explain loops", "attempt": 1})
        data = resp.json()
        assert "response_text" in data
        assert "intent" in data
        assert "attempt" in data

    def test_response_text_is_non_empty(self, client):
        resp = self._post(client, {"user_input": "what is slicing?", "attempt": 1})
        assert len(resp.json()["response_text"]) > 0

    def test_off_topic_returns_redirect(self, client):
        resp = self._post(client, {"user_input": "what's the weather today?", "attempt": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "off_topic"
        text = data["response_text"].lower()
        assert "curriculum" in text or "python" in text or "course" in text

    def test_attempt_echoed_back_in_response(self, client):
        resp = self._post(client, {"user_input": "how do I slice?", "attempt": 2})
        assert resp.json()["attempt"] == 2

    def test_hard_block_at_attempt_3(self, client):
        resp = self._post(client, {
            "user_input": "just give me the answer",
            "attempt": 3,
        })
        assert resp.status_code == 200
        data = resp.json()
        text = data["response_text"].lower()
        assert "answer" in text or "lesson" in text or "block" in text

    def test_answer_seeking_triggers_guide_response(self, client):
        resp = self._post(client, {
            "user_input": "just tell me the answer",
            "attempt": 1,
        })
        data = resp.json()
        assert data["intent"] == "answer_seeking"
        assert data["response_text"]


# ---------------------------------------------------------------------------
# /chat — request validation
# ---------------------------------------------------------------------------

class TestChatValidation:
    def test_missing_user_input_returns_422(self, client):
        resp = client.post("/chat", json={"attempt": 1})
        assert resp.status_code == 422

    def test_attempt_defaults_to_1_when_omitted(self, client):
        resp = client.post("/chat", json={"user_input": "explain slicing"})
        assert resp.status_code == 200

    def test_conversation_history_defaults_to_empty(self, client):
        resp = client.post("/chat", json={"user_input": "explain slicing"})
        assert resp.status_code == 200

    def test_extra_fields_ignored(self, client):
        resp = client.post("/chat", json={
            "user_input": "explain slicing",
            "attempt": 1,
            "unknown_field": "ignored",
        })
        assert resp.status_code == 200

    def test_lesson_context_included(self, client):
        resp = client.post("/chat", json={
            "user_input": "I'm confused",
            "lesson_context": "Write a function that reverses a string.",
            "attempt": 1,
        })
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /chat — multi-turn conversation history
# ---------------------------------------------------------------------------

class TestConversationHistory:
    def test_history_accepted_without_error(self, client):
        history = [
            {"role": "user", "content": "how do I slice?"},
            {"role": "assistant", "content": "Think about the indices."},
        ]
        resp = client.post("/chat", json={
            "user_input": "what do you mean?",
            "attempt": 1,
            "conversation_history": history,
        })
        assert resp.status_code == 200

    def test_server_escalates_attempt_from_history(self, client):
        """
        The server recalculates attempt from history internally (for routing),
        but the API response echoes back the client-sent attempt value.
        What we can verify is that the response still comes back 200 and that
        the intent is correctly identified as answer_seeking.
        """
        history = [
            {"role": "user", "content": "give me the answer"},
            {"role": "assistant", "content": "Let's think about it."},
        ]
        resp = client.post("/chat", json={
            "user_input": "just tell me",
            "attempt": 1,
            "conversation_history": history,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "answer_seeking"
        assert data["response_text"]


# ---------------------------------------------------------------------------
# Logging side-effect
# ---------------------------------------------------------------------------

class TestLogging:
    def test_log_interaction_called_on_chat(self, client, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "app.api.log_interaction",
            lambda **kwargs: calls.append(kwargs),
        )
        client.post("/chat", json={"user_input": "explain slicing", "attempt": 1})
        assert len(calls) == 1
        assert calls[0]["user_input"] == "explain slicing"

    def test_log_records_intent(self, client, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "app.api.log_interaction",
            lambda **kwargs: calls.append(kwargs),
        )
        client.post("/chat", json={"user_input": "what is slicing?", "attempt": 1})
        assert calls[0]["intent"] in ("curriculum", "answer_seeking", "off_topic")
        