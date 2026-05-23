"""
test_graph_integration.py — End-to-end LangGraph pipeline tests.

Runs the full compiled graph (retriever + Groq mocked) and verifies that the
correct node is reached and the response looks right for every escalation level.
"""

import pytest
from unittest.mock import MagicMock
from app.main import build_graph, PathwiseState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _groq_mock(content: str):
    msg = MagicMock(); msg.content = content
    choice = MagicMock(); choice.message = msg
    resp = MagicMock(); resp.choices = [choice]
    client = MagicMock()
    client.chat.completions.create.return_value = resp
    return client


CANNED_CHUNKS = [
    {
        "text": (
            "Week: week_01\nSection: ## Slicing\n---\n"
            "Use s[start:end] to slice a string."
        ),
        "week": "week_01",
        "topic": "Slicing",
    }
]


def make_state(user_input, attempt=1, history=None, intent="") -> PathwiseState:
    return PathwiseState(
        user_input=user_input,
        lesson_context='word = "cheese"',
        conversation_history=history or [],
        retrieved_chunks=[],
        intent=intent,
        attempt=attempt,
        response_text="",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def patched_graph(monkeypatch):
    safe_text = "What have you tried with string slicing? Review the Slicing section."
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(
        "guardrails.no_direct_answers.Groq",
        lambda **kwargs: _groq_mock(safe_text),
    )
    monkeypatch.setattr("app.main.retrieve", lambda query, k=3: CANNED_CHUNKS)
    return build_graph()


# ---------------------------------------------------------------------------
# Curriculum path
# ---------------------------------------------------------------------------

class TestCurriculumPath:
    def test_curriculum_question_returns_response(self, patched_graph):
        state = make_state("how does string slicing work?")
        result = patched_graph.invoke(state)
        assert result["response_text"]

    def test_curriculum_intent_set_correctly(self, patched_graph):
        state = make_state("how does string slicing work?")
        result = patched_graph.invoke(state)
        assert result["intent"] == "curriculum"

    def test_curriculum_response_is_not_fallback_boilerplate(self, patched_graph):
        state = make_state("explain the split method")
        result = patched_graph.invoke(state)
        # Ensure the pipeline actually produced something meaningful
        assert len(result["response_text"]) > 30


# ---------------------------------------------------------------------------
# Off-topic path
# ---------------------------------------------------------------------------

class TestOffTopicPath:
    def test_off_topic_returns_redirect(self, patched_graph):
        state = make_state("what's the weather in London?")
        result = patched_graph.invoke(state)
        assert result["intent"] == "off_topic"
        assert "Pathwise" in result["response_text"] or "curriculum" in result["response_text"].lower()

    def test_sports_question_is_off_topic(self, patched_graph):
        state = make_state("who won the game last night?")
        result = patched_graph.invoke(state)
        assert result["intent"] == "off_topic"


# ---------------------------------------------------------------------------
# Answer-seeking escalation path
# ---------------------------------------------------------------------------

class TestAnswerSeekingEscalation:
    def test_attempt_1_returns_guide_response(self, patched_graph):
        state = make_state("just tell me the answer", attempt=1)
        result = patched_graph.invoke(state)
        assert result["intent"] == "answer_seeking"
        assert result["response_text"]

    def test_attempt_2_returns_structured_hint(self, patched_graph, monkeypatch):
        hint_text = (
            "String slicing is the key concept. "
            "Try `'apple'[0:2]` for 'ap'. What indices do you need?"
        )
        monkeypatch.setattr(
            "guardrails.no_direct_answers.Groq",
            lambda **kwargs: _groq_mock(hint_text),
        )
        state = make_state("give me the solution", attempt=2)
        result = patched_graph.invoke(state)
        assert result["intent"] == "answer_seeking"
        assert result["response_text"]

    def test_attempt_3_triggers_hard_block(self, patched_graph):
        state = make_state("I need the answer now", attempt=3)
        result = patched_graph.invoke(state)
        assert result["intent"] == "answer_seeking"
        text = result["response_text"].lower()
        assert "answer" in text or "lesson" in text

    def test_hard_block_text_contains_suggestions(self, patched_graph):
        state = make_state("write the code for me", attempt=3)
        result = patched_graph.invoke(state)
        text = result["response_text"]
        # Hard block should suggest alternatives
        assert any(word in text.lower() for word in ["lesson", "review", "instructor", "material"])

    def test_attempt_escalates_from_history(self, patched_graph):
        """Server-side attempt re-count should push straight to hard block."""
        history = [
            {"role": "user", "content": "give me the answer"},
            {"role": "assistant", "content": "Let's think..."},
            {"role": "user", "content": "just tell me the answer"},
            {"role": "assistant", "content": "Try again..."},
        ]
        state = make_state("write the code for me", attempt=1, history=history)
        result = patched_graph.invoke(state)
        # 2 in history + 1 current = 3 → hard block territory
        assert result["attempt"] >= 3


# ---------------------------------------------------------------------------
# Multi-turn context threading
# ---------------------------------------------------------------------------

class TestMultiTurnContext:
    def test_follow_up_stays_on_topic(self, patched_graph):
        """'What do you mean?' after a slicing discussion should get slicing help."""
        history = [
            {"role": "user", "content": "how does slicing work?"},
            {"role": "assistant", "content": "String slicing uses s[start:end] notation."},
        ]
        state = make_state("what do you mean?", history=history)
        result = patched_graph.invoke(state)
        assert result["response_text"]
        assert result["intent"] == "curriculum"

    def test_curriculum_response_after_prior_answer_seeking(self, patched_graph):
        """After prior answer-seeking, a genuine curriculum question should still get help."""
        history = [
            {"role": "user", "content": "just tell me the answer"},
            {"role": "assistant", "content": "I won't give the answer directly..."},
        ]
        state = make_state("can you explain what a list is?", attempt=1, history=history)
        result = patched_graph.invoke(state)
        # Still a valid curriculum question — should get a response
        assert result["response_text"]


# ---------------------------------------------------------------------------
# State passthrough integrity
# ---------------------------------------------------------------------------

class TestStateIntegrity:
    def test_response_text_always_set(self, patched_graph):
        for input_text in [
            "how does slicing work?",
            "just give me the answer",
            "what's the weather?",
            "write the code for me",
        ]:
            state = make_state(input_text, attempt=3)
            result = patched_graph.invoke(state)
            assert result["response_text"], f"Empty response for: {input_text!r}"

    def test_intent_always_one_of_three_values(self, patched_graph):
        valid_intents = {"curriculum", "answer_seeking", "off_topic"}
        for input_text in [
            "explain loops",
            "tell me the answer",
            "recommend a movie",
        ]:
            state = make_state(input_text)
            result = patched_graph.invoke(state)
            assert result["intent"] in valid_intents, (
                f"Unexpected intent '{result['intent']}' for: {input_text!r}"
            )
            