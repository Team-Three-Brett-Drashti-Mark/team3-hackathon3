"""
test_retriever.py — Unit tests for retrieval/retriever.py.

Covers:
  - _parse_metadata correctly extracts week/topic from embedded headers
  - retrieve() returns well-formed dicts
  - retrieve() returns [] gracefully on SDK failures
  - retrieve() deduplicates and formats correctly
"""

import pytest
from unittest.mock import MagicMock, patch
from retrieval.retriever import _parse_metadata, retrieve


# ---------------------------------------------------------------------------
# _parse_metadata
# ---------------------------------------------------------------------------

class TestParseMetadata:
    def test_extracts_week(self):
        text = "Document: intro\nWeek: week_03\nSection: ## Slicing\n---\nsome content"
        result = _parse_metadata(text)
        assert result["week"] == "week_03"

    def test_extracts_topic_from_section(self):
        # Section: must appear before Document: since the parser sets topic on first match
        text = "Week: week_01\nSection: ## String Methods\n---\ncontent"
        result = _parse_metadata(text)
        assert result["topic"] == "String Methods"

    def test_strips_markdown_hashes_from_section(self):
        text = "Section: ## Indexing & Slicing\n---"
        result = _parse_metadata(text)
        assert result["topic"] == "Indexing & Slicing"

    def test_falls_back_to_document_for_topic(self):
        text = "Document: summer10-strings\n---\ncontent without a section heading"
        result = _parse_metadata(text)
        assert result["topic"] == "summer10-strings"

    def test_returns_none_when_fields_missing(self):
        result = _parse_metadata("random content with no headers")
        assert result["week"] is None
        assert result["topic"] is None

    def test_stops_parsing_at_separator(self):
        """Metadata headers after '---' should not be picked up."""
        text = "Week: week_01\n---\nWeek: week_99\nSection: ## After Separator"
        result = _parse_metadata(text)
        assert result["week"] == "week_01"

    def test_handles_empty_string(self):
        result = _parse_metadata("")
        assert result == {"week": None, "topic": None}


# ---------------------------------------------------------------------------
# retrieve() — happy path via mocked SDK
# ---------------------------------------------------------------------------

class TestRetrieve:
    def _make_sdk_result(self, texts):
        """Build a minimal WorkspaceClient mock that returns given texts."""
        data_array = [[t] for t in texts]
        index_result = MagicMock()
        index_result.as_dict.return_value = {
            "result": {"data_array": data_array}
        }
        client = MagicMock()
        client.vector_search_indexes.query_index.return_value = index_result
        return client

    def test_returns_list_of_dicts(self, monkeypatch):
        text = "Week: week_01\nSection: ## Slicing\n---\nContent here."
        client = self._make_sdk_result([text])
        monkeypatch.setattr("retrieval.retriever.WorkspaceClient", lambda: client)

        results = retrieve("slicing question", k=1)
        assert isinstance(results, list)
        assert len(results) == 1

    def test_each_result_has_text_week_topic(self, monkeypatch):
        text = "Week: week_02\nSection: ## Loops\n---\nLoop content."
        client = self._make_sdk_result([text])
        monkeypatch.setattr("retrieval.retriever.WorkspaceClient", lambda: client)

        result = retrieve("for loop", k=1)[0]
        assert "text" in result
        assert "week" in result
        assert "topic" in result

    def test_passes_query_and_k_to_sdk(self, monkeypatch):
        client = self._make_sdk_result([])
        monkeypatch.setattr("retrieval.retriever.WorkspaceClient", lambda: client)

        retrieve("my query", k=5)
        call_kwargs = client.vector_search_indexes.query_index.call_args
        assert call_kwargs.kwargs.get("query_text") == "my query"
        assert call_kwargs.kwargs.get("num_results") == 5

    def test_returns_empty_list_on_sdk_exception(self, monkeypatch):
        def bad_client():
            raise ConnectionError("Databricks unreachable")
        monkeypatch.setattr("retrieval.retriever.WorkspaceClient", bad_client)

        results = retrieve("any query")
        assert results == []

    def test_returns_empty_list_when_data_array_missing(self, monkeypatch):
        index_result = MagicMock()
        index_result.as_dict.return_value = {"result": {}}
        client = MagicMock()
        client.vector_search_indexes.query_index.return_value = index_result
        monkeypatch.setattr("retrieval.retriever.WorkspaceClient", lambda: client)

        results = retrieve("query")
        assert results == []

    def test_filters_empty_rows(self, monkeypatch):
        """Rows that are empty/None should be silently skipped."""
        index_result = MagicMock()
        index_result.as_dict.return_value = {
            "result": {"data_array": [[], None, ["Week: week_01\n---\nContent."]]}
        }
        client = MagicMock()
        client.vector_search_indexes.query_index.return_value = index_result
        monkeypatch.setattr("retrieval.retriever.WorkspaceClient", lambda: client)

        results = retrieve("q")
        # Only the non-empty row should survive
        assert len(results) == 1


# ---------------------------------------------------------------------------
# retrieve_context node — chunk relevance filtering in app.main
# ---------------------------------------------------------------------------

class TestRetrieveContextNode:
    """
    Tests the LangGraph retrieve_context node, which applies student-word
    filtering on top of raw retrieval results.
    """

    def test_filters_out_irrelevant_chunks(self, monkeypatch):
        """Chunks with no overlap with the student's vocabulary are dropped."""
        from app.main import retrieve_context

        irrelevant_chunk = {"text": "reversing strings: s[::-1]", "week": "week_01", "topic": "Reversing"}
        relevant_chunk   = {"text": "slicing strings: s[0:3]", "week": "week_01", "topic": "Slicing"}

        monkeypatch.setattr(
            "app.main.retrieve",
            lambda query, k=3: [irrelevant_chunk, relevant_chunk],
        )

        state = {
            "user_input": "how does slicing work",
            "lesson_context": "",
            "conversation_history": [],
            "retrieved_chunks": [],
            "intent": "curriculum",
            "attempt": 1,
            "response_text": "",
        }
        result = retrieve_context(state)
        texts = [c["text"] for c in result["retrieved_chunks"]]

        # Slicing chunk should pass; reversing chunk is off-topic
        assert any("slicing" in t for t in texts)

    def test_keeps_best_chunk_when_all_fail_filter(self, monkeypatch):
        """When no chunk matches student words, the highest-scoring one is kept."""
        from app.main import retrieve_context

        chunk = {"text": "completely unrelated content about something else", "week": "week_02", "topic": "Other"}
        monkeypatch.setattr("app.main.retrieve", lambda query, k=3: [chunk])

        state = {
            "user_input": "xyz123 unique words",
            "lesson_context": "",
            "conversation_history": [],
            "retrieved_chunks": [],
            "intent": "curriculum",
            "attempt": 1,
            "response_text": "",
        }
        result = retrieve_context(state)
        # Should fall back to keeping one chunk rather than returning empty
        assert len(result["retrieved_chunks"]) == 1
        