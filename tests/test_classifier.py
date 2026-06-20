"""
test_classifier.py — Unit tests for classify_intent and route_intent.

Covers every branch: curriculum, answer_seeking, off_topic, attempt escalation,
and the server-side history re-count that prevents frontend drift.
"""

import pytest
from app.main import classify_intent, route_intent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def state(user_input, attempt=1, history=None):
    return {
        "user_input": user_input,
        "lesson_context": "",
        "conversation_history": history or [],
        "retrieved_chunks": [],
        "intent": "",
        "attempt": attempt,
        "response_text": "",
    }


def apply_classify(user_input, attempt=1, history=None):
    s = state(user_input, attempt, history)
    return {**s, **classify_intent(s)}


# ---------------------------------------------------------------------------
# Intent classification — curriculum
# ---------------------------------------------------------------------------

class TestCurriculumIntent:
    def test_simple_concept_question(self):
        result = apply_classify("how does string slicing work?")
        assert result["intent"] == "curriculum"

    def test_error_message_question(self):
        result = apply_classify("why am I getting an IndexError?")
        assert result["intent"] == "curriculum"

    def test_ask_about_method(self):
        result = apply_classify("what does .split() do?")
        assert result["intent"] == "curriculum"

    def test_empty_like_question(self):
        result = apply_classify("what?")
        assert result["intent"] == "curriculum"

    def test_follow_up_phrasing(self):
        result = apply_classify("can you explain that more?")
        assert result["intent"] == "curriculum"


# ---------------------------------------------------------------------------
# Intent classification — answer_seeking
# ---------------------------------------------------------------------------

class TestAnswerSeekingIntent:
    @pytest.mark.parametrize("phrase", [
        "what is the answer",
        "give me the answer",
        "just tell me",
        "write the code for me",
        "what's the solution",
        "I need the answer",
        "just give me",
        "can you just give me the code",
        "tell me the answer",
        "do it for me",
    ])
    def test_keyword_triggers(self, phrase):
        result = apply_classify(phrase)
        assert result["intent"] == "answer_seeking", f"Expected answer_seeking for: {phrase!r}"

    def test_mixed_curriculum_and_answer_seeking_prefers_answer(self):
        # If the phrase contains an answer-seeking keyword it should win
        result = apply_classify("I understand slicing but just give me the code")
        assert result["intent"] == "answer_seeking"


# ---------------------------------------------------------------------------
# Intent classification — off_topic
# ---------------------------------------------------------------------------

class TestOffTopicIntent:
    @pytest.mark.parametrize("phrase", [
        "what's the weather like today",
        "tell me about the latest sports news",
        "recommend a movie",
        "what's a good recipe for pasta",
        "crypto prices",
    ])
    def test_off_topic_keywords(self, phrase):
        result = apply_classify(phrase)
        assert result["intent"] == "off_topic", f"Expected off_topic for: {phrase!r}"

    @pytest.mark.parametrize("phrase", [
        "🔥💀🌈",                 # emoji-only
        "हाय आप कैसे हैं",        # Devanagari (Hindi) — no Latin letters
        "你好吗",                  # Han script
        "!?!? ...",               # punctuation/symbols only
        "1234 5678",              # digits only
        "",                       # empty
    ])
    def test_non_latin_or_symbol_only_is_off_topic(self, phrase):
        # Messages with no Latin-script letters can't be curriculum questions and
        # must never reach the LLM — they previously defaulted to curriculum.
        result = apply_classify(phrase)
        assert result["intent"] == "off_topic", f"Expected off_topic for: {phrase!r}"

    def test_mixed_script_with_latin_word_still_classifies_normally(self):
        # A message containing a real Latin/Python word is a legitimate question
        # even if it also includes non-Latin characters.
        result = apply_classify("हाय print() कैसे काम करता है")
        assert result["intent"] == "curriculum"


# ---------------------------------------------------------------------------
# Attempt escalation
# ---------------------------------------------------------------------------

class TestAttemptEscalation:
    def test_attempt_stays_at_1_for_curriculum(self):
        result = apply_classify("how does slicing work?", attempt=1)
        assert result["attempt"] == 1

    def test_attempt_passed_through_for_curriculum(self):
        result = apply_classify("explain loops", attempt=2)
        assert result["attempt"] == 2

    def test_server_increments_attempt_from_history(self):
        """
        Server counts answer-seeking turns in history and bumps attempt above
        whatever the client sent — prevents frontend drift.
        """
        history = [
            {"role": "user", "content": "just tell me the answer"},
            {"role": "assistant", "content": "Let's think about it..."},
        ]
        result = apply_classify("give me the answer", attempt=1, history=history)
        # history has 1 prior answer-seeking + current = 2
        assert result["attempt"] >= 2

    def test_server_attempt_cannot_go_below_client(self):
        """Client-sent attempt is the floor — server only raises, never lowers."""
        result = apply_classify("how do loops work?", attempt=3)
        assert result["attempt"] == 3


# ---------------------------------------------------------------------------
# route_intent
# ---------------------------------------------------------------------------

class TestRouteIntent:
    def _state_with_intent(self, intent, attempt=1):
        return {
            "user_input": "test",
            "intent": intent,
            "attempt": attempt,
            "conversation_history": [],
            "retrieved_chunks": [],
            "lesson_context": "",
            "response_text": "",
        }

    def test_off_topic_routes_to_handler(self):
        s = self._state_with_intent("off_topic")
        assert route_intent(s) == "off_topic_handler"

    def test_curriculum_routes_to_retrieve(self):
        s = self._state_with_intent("curriculum")
        assert route_intent(s) == "retrieve_context"

    def test_answer_seeking_attempt1_routes_to_retrieve(self):
        s = self._state_with_intent("answer_seeking", attempt=1)
        assert route_intent(s) == "retrieve_context"

    def test_answer_seeking_attempt2_routes_to_retrieve(self):
        s = self._state_with_intent("answer_seeking", attempt=2)
        assert route_intent(s) == "retrieve_context"

    def test_answer_seeking_attempt3_routes_to_hard_block(self):
        s = self._state_with_intent("answer_seeking", attempt=3)
        assert route_intent(s) == "hard_block"

    def test_answer_seeking_attempt_above3_also_hard_blocks(self):
        s = self._state_with_intent("answer_seeking", attempt=99)
        assert route_intent(s) == "hard_block"
        