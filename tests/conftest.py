"""
conftest.py — Shared fixtures for all Pathwise tests.

Patches external dependencies (Groq, Databricks) so tests run fully offline.
"""

import sys
import os
from unittest.mock import MagicMock

# Add the project root to sys.path so `from app.main import ...` works
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Stub out heavy cloud dependencies BEFORE any project module is imported.
# retrieval/retriever.py does `from databricks.sdk import WorkspaceClient` at
# the top level, so it fails at collection time if databricks isn't installed.
# Injecting fake modules into sys.modules prevents that import from ever
# reaching the real package.
# ---------------------------------------------------------------------------

# The stub must mirror the SUBMODULE paths the app imports, not just the top
# package. app/admin.py and app/logger.py do
#   from databricks.sdk.service.sql import StatementResponse, StatementState
# so a bare `databricks.sdk` MagicMock isn't enough — Python then tries to import
# the real `databricks.sdk.service.sql` submodule and fails with "not a package".
# We therefore register every dotted level we import from. StatementState is
# accessed as an enum (StatementState.SUCCEEDED, etc.); MagicMock caches attribute
# access, so each member is a stable object and set membership works.
_databricks_sdk = MagicMock()
_databricks_sdk.WorkspaceClient = MagicMock
_databricks_sql = MagicMock()  # stands in for databricks.sdk.service.sql
sys.modules.setdefault("databricks", MagicMock())
sys.modules.setdefault("databricks.sdk", _databricks_sdk)
sys.modules.setdefault("databricks.sdk.service", MagicMock())
sys.modules.setdefault("databricks.sdk.service.sql", _databricks_sql)
sys.modules.setdefault("databricks.vectorsearch", MagicMock())
sys.modules.setdefault("databricks.vectorsearch.client", MagicMock())

_groq_mod = MagicMock()
_groq_mod.Groq = MagicMock
sys.modules.setdefault("groq", _groq_mod)

import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Fake LLM response helpers
# ---------------------------------------------------------------------------

def _make_groq_response(content: str):
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _safe_guide_reply():
    return _make_groq_response(
        "Let's think about this together. What have you already tried with string slicing? "
        "Review the 'Slicing' section in your lesson panel."
    )


def _safe_curriculum_reply():
    return _make_groq_response(
        "String slicing lets you extract a portion of a string using bracket notation. "
        "For example, `'hello'[1:3]` returns `'el'`. "
        "How would you apply this to extract the first three characters?"
    )


def _safe_hint_reply():
    return _make_groq_response(
        "The concept you need is string slicing. "
        "It works like `word[start:end]`. "
        "For example, `'apple'[0:2]` gives `'ap'`. "
        "Given that, what indexes would give you the first three characters?"
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_groq(monkeypatch):
    """Patch Groq so no real API calls are made. Returns the mock client."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _safe_guide_reply()
    monkeypatch.setattr(
        "guardrails.no_direct_answers.Groq",
        lambda **kwargs: mock_client,
    )
    return mock_client


@pytest.fixture
def mock_retriever(monkeypatch):
    """Patch the Databricks vector-search retriever with canned curriculum chunks."""
    chunks = [
        {
            "text": (
                "Document: summer10-strings-nup\n"
                "Section: Slicing\n"
                "Week: week_01\n"
                "---\n"
                "String slicing lets you extract part of a string. "
                "Use s[start:end] where start is inclusive and end is exclusive."
            ),
            "week": "week_01",
            "topic": "Slicing",
        }
    ]
    monkeypatch.setattr("app.main.retrieve", lambda query, k=3: chunks)
    return chunks


@pytest.fixture
def base_state():
    """Minimal valid PathwiseState for unit tests."""
    return {
        "user_input": "how do I slice a string?",
        "lesson_context": 'Slice the first three characters from: word = "cheese"',
        "conversation_history": [],
        "retrieved_chunks": [],
        "intent": "",
        "attempt": 1,
        "response_text": "",
    }


@pytest.fixture
def graph(mock_retriever):
    """Build and return the compiled LangGraph (retriever patched)."""
    from app.main import build_graph
    return build_graph()
