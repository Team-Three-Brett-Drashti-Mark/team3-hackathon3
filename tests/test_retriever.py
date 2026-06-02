"""
test_retriever.py — Unit tests for retrieval/retriever.py.

Covers:
  - _parse_metadata correctly extracts week/topic from the metadata JSON column
  - retrieve() returns well-formed dicts (text, week, topic, score)
  - retrieve() returns [] gracefully on SDK failures
  - retrieve_context gates chunks on vector-search relevance score
"""

import pytest
from unittest.mock import MagicMock, patch
from retrieval.retriever import _parse_metadata, retrieve


# ---------------------------------------------------------------------------
# _parse_metadata
# ---------------------------------------------------------------------------

class TestParseMetadata:
    def test_extracts_week(self):
        meta = '{"doc_title":"intro","week":"week_03","section_title":"## Slicing"}'
        result = _parse_metadata(meta)
        assert result["week"] == "week_03"

    def test_extracts_topic_from_section(self):
        # Section heading is the most specific label, preferred over topic/doc_title
        meta = '{"week":"week_01","section_title":"## String Methods","topic":"intro_to_strings"}'
        result = _parse_metadata(meta)
        assert result["topic"] == "String Methods"

    def test_strips_markdown_hashes_from_section(self):
        meta = '{"section_title":"## Indexing & Slicing"}'
        result = _parse_metadata(meta)
        assert result["topic"] == "Indexing & Slicing"

    def test_falls_back_to_topic_then_doc_title(self):
        # No section_title → fall back to the explicit topic field, then doc_title
        meta = '{"doc_title":"summer10-strings","topic":"strings_overview"}'
        result = _parse_metadata(meta)
        assert result["topic"] == "strings_overview"

    def test_skips_pdf_content_placeholder(self):
        # "PDF Content" is a generic placeholder the PDF chunker writes, not a real
        # heading — PDF chunks should attribute to their doc_title instead.
        meta = '{"doc_title":"Strings-Cheatsheet","section_title":"PDF Content","topic":"Strings-Cheatsheet"}'
        result = _parse_metadata(meta)
        assert result["topic"] == "Strings-Cheatsheet"

    def test_returns_none_when_fields_missing(self):
        result = _parse_metadata('{"content_type":"markdown"}')
        assert result["week"] is None
        assert result["topic"] is None

    def test_handles_malformed_json(self):
        # Defensive: a non-JSON blob degrades to unattributed, never raises.
        result = _parse_metadata("not valid json {{{")
        assert result == {"week": None, "topic": None}

    def test_handles_empty_string(self):
        result = _parse_metadata("")
        assert result == {"week": None, "topic": None}


# ---------------------------------------------------------------------------
# retrieve() — happy path via mocked SDK
# ---------------------------------------------------------------------------

class TestRetrieve:
    def _make_sdk_result(self, texts, metadata='{"week":"week_01","section_title":"## Slicing"}', score=0.8):
        """Build a minimal WorkspaceClient mock returning [text, metadata, score] rows.

        Mirrors the real index shape: each row is the requested columns
        (text, metadata) with the relevance score appended last.
        """
        data_array = [[t, metadata, score] for t in texts]
        index_result = MagicMock()
        index_result.as_dict.return_value = {
            "result": {"data_array": data_array}
        }
        client = MagicMock()
        client.vector_search_indexes.query_index.return_value = index_result
        return client

    def test_returns_list_of_dicts(self, monkeypatch):
        client = self._make_sdk_result(["Slicing content here."])
        monkeypatch.setattr("retrieval.retriever.WorkspaceClient", lambda: client)

        results = retrieve("slicing question", k=1)
        assert isinstance(results, list)
        assert len(results) == 1

    def test_each_result_has_text_week_topic_score(self, monkeypatch):
        client = self._make_sdk_result(
            ["Loop content."],
            metadata='{"week":"week_02","section_title":"## Loops"}',
            score=0.77,
        )
        monkeypatch.setattr("retrieval.retriever.WorkspaceClient", lambda: client)

        result = retrieve("for loop", k=1)[0]
        # Metadata is now parsed from the JSON column, and the score is surfaced
        assert result["text"] == "Loop content."
        assert result["week"] == "week_02"
        assert result["topic"] == "Loops"
        assert result["score"] == 0.77

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
            "result": {"data_array": [[], None, ["Content.", '{"week":"week_01"}', 0.8]]}
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

        # Both clear the relevance-score gate (>= MIN_RELEVANCE_SCORE); the
        # student-word filter is what decides between them.
        irrelevant_chunk = {"text": "reversing strings: s[::-1]", "week": "week_01", "topic": "Reversing", "score": 0.7}
        relevant_chunk   = {"text": "slicing strings: s[0:3]", "week": "week_01", "topic": "Slicing", "score": 0.7}

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

        # Clears the relevance-score gate, but shares no words with the student's
        # message — exercises the keyword-filter fallback that keeps the best chunk.
        chunk = {"text": "completely unrelated content about something else", "week": "week_02", "topic": "Other", "score": 0.7}
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

    def test_drops_chunks_below_relevance_score(self, monkeypatch):
        """Out-of-corpus questions return low-score chunks, which must be dropped.

        This is the guard against hallucinated grounding: when only week_01
        strings is indexed, a recursion question still returns the nearest
        strings chunks but at a low score. Gating them out leaves no grounding,
        so the LLM can decline honestly instead of inventing a citation.
        """
        from app.main import retrieve_context, MIN_RELEVANCE_SCORE

        low = MIN_RELEVANCE_SCORE - 0.05
        weak_chunk = {"text": "string slicing content", "week": "week_01", "topic": "Slicing", "score": low}
        monkeypatch.setattr("app.main.retrieve", lambda query, k=3: [weak_chunk])

        state = {
            "user_input": "how do I write a recursive function",
            "lesson_context": "",
            "conversation_history": [],
            "retrieved_chunks": [],
            "intent": "curriculum",
            "attempt": 1,
            "response_text": "",
        }
        result = retrieve_context(state)
        assert result["retrieved_chunks"] == []
        