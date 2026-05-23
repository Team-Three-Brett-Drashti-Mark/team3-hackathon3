"""
test_guardrails.py — Unit tests for guardrail response nodes.

Verifies:
  - curriculum_response, guide_response, structured_hint return text
  - hard_block returns static text, never calls the LLM
  - answer-leak detection swaps in fallback when the LLM misbehaves
  - off_topic_handler always redirects correctly
"""

import pytest
from unittest.mock import MagicMock
from guardrails.no_direct_answers import (
    curriculum_response,
    guide_response,
    structured_hint,
    hard_block,
    _leaks_answer,
    _GUIDE_FALLBACK,
    _HINT_FALLBACK,
    _CURRICULUM_FALLBACK,
)
from app.main import off_topic_handler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_groq_response(content):
    msg = MagicMock(); msg.content = content
    choice = MagicMock(); choice.message = msg
    resp = MagicMock(); resp.choices = [choice]
    return resp


def base_state(user_input="how do I slice a string?", attempt=1, history=None, chunks=None):
    return {
        "user_input": user_input,
        "lesson_context": 'Slice the first three characters from: word = "cheese"',
        "conversation_history": history or [],
        "retrieved_chunks": chunks or [
            {"text": "String slicing: s[start:end]", "week": "week_01", "topic": "Slicing"}
        ],
        "intent": "curriculum",
        "attempt": attempt,
        "response_text": "",
    }


# ---------------------------------------------------------------------------
# Answer-leak detection
# ---------------------------------------------------------------------------

class TestLeakDetection:
    @pytest.mark.parametrize("bad_text", [
        "```python\nword[:3]\n```",
        "The answer is `word[:3]`",
        "It would return 'che'",
        "it returns the substring",
        "the result is cheese[:3]",
        "the output is 'che'",
        "Here's the code: word[:3]",
        "here is the code",
        "will return 'che'",
        "will print the value",
    ])
    def test_detects_leaking_content(self, bad_text):
        assert _leaks_answer(bad_text), f"Should detect leak in: {bad_text!r}"

    @pytest.mark.parametrize("safe_text", [
        "What have you tried so far with string slicing?",
        "Review the slicing section in your lesson panel.",
        "Think about the start and end indexes you need.",
        "Think about which index positions you need for the first three characters.",
    ])
    def test_allows_safe_content(self, safe_text):
        assert not _leaks_answer(safe_text), f"Should NOT flag safe text: {safe_text!r}"


# ---------------------------------------------------------------------------
# hard_block — no LLM call, static message
# ---------------------------------------------------------------------------

class TestHardBlock:
    def test_returns_response_text(self):
        result = hard_block(base_state(attempt=3))
        assert "response_text" in result
        assert len(result["response_text"]) > 20

    def test_message_mentions_direct_answer(self):
        result = hard_block(base_state(attempt=3))
        text = result["response_text"].lower()
        assert "direct answer" in text or "answer" in text

    def test_message_suggests_review(self):
        result = hard_block(base_state(attempt=3))
        text = result["response_text"].lower()
        assert "lesson" in text or "review" in text or "material" in text

    def test_no_llm_call_made(self, monkeypatch):
        """hard_block must be a pure static response — never touch the LLM."""
        called = []
        monkeypatch.setattr(
            "guardrails.no_direct_answers.Groq",
            lambda **kwargs: (_ for _ in ()).throw(AssertionError("hard_block called Groq!")),
        )
        # Should not raise
        result = hard_block(base_state(attempt=3))
        assert result["response_text"]


# ---------------------------------------------------------------------------
# off_topic_handler
# ---------------------------------------------------------------------------

class TestOffTopicHandler:
    def test_returns_redirect_message(self):
        result = off_topic_handler(base_state())
        assert "response_text" in result

    def test_message_mentions_curriculum(self):
        text = off_topic_handler(base_state())["response_text"].lower()
        assert "curriculum" in text or "course" in text or "python" in text

    def test_message_mentions_pathwise(self):
        text = off_topic_handler(base_state())["response_text"]
        assert "Pathwise" in text


# ---------------------------------------------------------------------------
# guide_response — safe LLM output passes through
# ---------------------------------------------------------------------------

class TestGuideResponse:
    def test_returns_llm_content_when_safe(self, monkeypatch):
        safe = "What part of string slicing have you tried? Review the Slicing section."
        mock = MagicMock()
        mock.chat.completions.create.return_value = _make_groq_response(safe)
        monkeypatch.setattr("guardrails.no_direct_answers.Groq", lambda **kwargs: mock)
        monkeypatch.setenv("GROQ_API_KEY", "test-key")

        result = guide_response(base_state())
        assert result["response_text"] == safe

    def test_fallback_on_code_leak(self, monkeypatch):
        leaky = "The answer is ```python\nword[:3]\n```"
        mock = MagicMock()
        mock.chat.completions.create.return_value = _make_groq_response(leaky)
        monkeypatch.setattr("guardrails.no_direct_answers.Groq", lambda **kwargs: mock)
        monkeypatch.setenv("GROQ_API_KEY", "test-key")

        result = guide_response(base_state())
        assert result["response_text"] == _GUIDE_FALLBACK

    def test_fallback_on_backtick_code(self, monkeypatch):
        leaky = "Just use `word[:3]` and you're done."
        mock = MagicMock()
        mock.chat.completions.create.return_value = _make_groq_response(leaky)
        monkeypatch.setattr("guardrails.no_direct_answers.Groq", lambda **kwargs: mock)
        monkeypatch.setenv("GROQ_API_KEY", "test-key")

        result = guide_response(base_state())
        assert result["response_text"] == _GUIDE_FALLBACK

    def test_includes_conversation_history_in_messages(self, monkeypatch):
        """Verify history turns are threaded into the Groq call."""
        captured_messages = []

        def fake_create(model, messages):
            captured_messages.extend(messages)
            return _make_groq_response("What have you tried?")

        mock = MagicMock()
        mock.chat.completions.create.side_effect = fake_create
        monkeypatch.setattr("guardrails.no_direct_answers.Groq", lambda **kwargs: mock)
        monkeypatch.setenv("GROQ_API_KEY", "test-key")

        history = [
            {"role": "user", "content": "I tried word[0:3]"},
            {"role": "assistant", "content": "Good start! What happened?"},
        ]
        guide_response(base_state(history=history))

        roles = [m["role"] for m in captured_messages]
        assert "assistant" in roles  # history included
        assert roles[-1] == "user"   # current message is last

    def test_raises_without_api_key(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.setattr(
            "guardrails.no_direct_answers.Groq",
            lambda **kwargs: (_ for _ in ()).throw(ValueError("GROQ_API_KEY is not set")),
        )
        with pytest.raises((ValueError, Exception)):
            guide_response(base_state())


# ---------------------------------------------------------------------------
# structured_hint — attempt 2
# ---------------------------------------------------------------------------

class TestStructuredHint:
    def test_returns_safe_content(self, monkeypatch):
        safe = (
            "String slicing is the key concept here. "
            "It works by specifying a start and end position in brackets. "
            "Given your string, what indices would you use?"
        )
        mock = MagicMock()
        mock.chat.completions.create.return_value = _make_groq_response(safe)
        monkeypatch.setattr("guardrails.no_direct_answers.Groq", lambda **kwargs: mock)
        monkeypatch.setenv("GROQ_API_KEY", "test-key")

        result = structured_hint(base_state(attempt=2))
        assert result["response_text"] == safe

    def test_fallback_on_direct_answer_leak(self, monkeypatch):
        leaky = "The answer is word[:3] which will print 'che'."
        mock = MagicMock()
        mock.chat.completions.create.return_value = _make_groq_response(leaky)
        monkeypatch.setattr("guardrails.no_direct_answers.Groq", lambda **kwargs: mock)
        monkeypatch.setenv("GROQ_API_KEY", "test-key")

        result = structured_hint(base_state(attempt=2))
        assert result["response_text"] == _HINT_FALLBACK


# ---------------------------------------------------------------------------
# curriculum_response — stricter leak check (only explicit answer phrases)
# ---------------------------------------------------------------------------

class TestCurriculumResponse:
    def test_safe_content_with_example_code_passes(self, monkeypatch):
        # curriculum_response allows method-name backticks, just not full answers
        safe = (
            "The `.split()` method divides a string at a delimiter. "
            "For example, `'a,b,c'.split(',')` gives `['a', 'b', 'c']`. "
            "How would you apply this to your problem?"
        )
        mock = MagicMock()
        mock.chat.completions.create.return_value = _make_groq_response(safe)
        monkeypatch.setattr("guardrails.no_direct_answers.Groq", lambda **kwargs: mock)
        monkeypatch.setenv("GROQ_API_KEY", "test-key")

        result = curriculum_response(base_state())
        assert result["response_text"] == safe

    def test_fallback_on_explicit_answer_phrase(self, monkeypatch):
        leaky = "Here's the complete answer: word[:3]"
        mock = MagicMock()
        mock.chat.completions.create.return_value = _make_groq_response(leaky)
        monkeypatch.setattr("guardrails.no_direct_answers.Groq", lambda **kwargs: mock)
        monkeypatch.setenv("GROQ_API_KEY", "test-key")

        result = curriculum_response(base_state())
        assert result["response_text"] == _CURRICULUM_FALLBACK
        