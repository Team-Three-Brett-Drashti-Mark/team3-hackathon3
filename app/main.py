import re
from typing import TypedDict, Literal
from langgraph.graph import END, START, StateGraph
from dotenv import load_dotenv
import os

# Load environment variables from .env (works from any working directory)
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(_env_path)

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from guardrails.no_direct_answers import curriculum_response, guide_response, structured_hint, hard_block
from retrieval.retriever import retrieve


# =============================================================================
# State
# =============================================================================

class PathwiseState(TypedDict):
    user_input: str              # Raw message from the student
    lesson_context: str          # Problem/exercise text the student is working on
    # Prior turns sent from the frontend: [{"role": "user"|"assistant", "content": str}].
    # Capped to the last 6 turns in _build_messages() to keep token usage bounded.
    conversation_history: list
    retrieved_chunks: list       # Relevant curriculum chunks from vector search
    intent: str                  # "answer_seeking" | "curriculum" | "off_topic"
    attempt: int                 # Guardrail escalation counter (1 → 2 → 3)
    response_text: str           # Final response sent back to the student


# =============================================================================
# Classifier & Router Nodes
# =============================================================================

_ANSWER_SEEKING_KEYWORDS = [
    "what is the answer", "give me the answer", "just tell me",
    "what's the solution", "what is the solution", "solve this for me",
    "write the code", "write me the code", "do it for me", "show me the solution",
    "answer is", "what should i write", "what do i write", "give me the code",
    "i want the answer", "want the answer", "i need the answer", "need the answer",
    "can i have the answer", "just have the answer", "just code it", "code it for me",
    "just show me", "tell me the answer", "give me the solution", "just give me",
    "can you just give", "just need the answer", "give me an answer",
]

_OFF_TOPIC_KEYWORDS = [
    "weather", "sports", "news", "movie", "music", "game", "recipe",
    "politics", "stock", "crypto", "dating", "taxes", "celebrity", "fashion", "travel", "fitness", "diet", "horoscope",
    "podcast", "streaming", "concert", "festival",  "mortgage", "insurance", "shopping", "coupon", "lottery", "gambling", "social media", "meme", "viral", "influencer", "youtube", "tiktok", "religion", "astrology", "conspiracy", "election", "war", "lawsuit", "relationship", "parenting", "pets", "gardening", "diy", "car",
]


def classify_intent(state: PathwiseState) -> dict:
    """Routes the student message to one of three intents."""
    text = state["user_input"].lower()
    if any(kw in text for kw in _ANSWER_SEEKING_KEYWORDS):
        intent = "answer_seeking"
    elif any(kw in text for kw in _OFF_TOPIC_KEYWORDS):
        intent = "off_topic"
    else:
        intent = "curriculum"

    # Server-side escalation: count answer-seeking turns already in history so
    # the attempt counter is correct even when the frontend falls behind.
    history = state.get("conversation_history") or []
    history_count = sum(
        1 for t in history
        if t.get("role") == "user"
        and any(kw in t.get("content", "").lower() for kw in _ANSWER_SEEKING_KEYWORDS)
    )
    server_attempt = history_count + (1 if intent == "answer_seeking" else 0)
    attempt = max(state.get("attempt", 1), server_attempt)

    return {"intent": intent, "attempt": attempt}


def off_topic_handler(_state: PathwiseState) -> dict:
    return {
        "response_text": (
            "I'm Pathwise, your Python learning assistant! "
            "I can only help with questions related to your curriculum and course material. "
            "Feel free to ask me about Python concepts, your assignments, or anything in the lesson panel. 📖"
        )
    }


def retrieve_context(state: PathwiseState) -> dict:
    """Fetch relevant curriculum chunks from Databricks Vector Search."""
    query = state["user_input"]
    if state.get("lesson_context"):
        query = f"{state['lesson_context']}\n{query}"

    # Without history, a vague follow-up like "what do you mean?" sends a
    # useless query to vector search and pulls unrelated curriculum chunks.
    # Prepending the last assistant turn anchors the query to the actual topic
    # so RAG retrieves the same concept that was already being discussed.
    history = state.get("conversation_history") or []
    prior_assistant = next(
        (m["content"] for m in reversed(history) if m["role"] == "assistant"), None
    )
    if prior_assistant:
        query = f"{prior_assistant}\n{query}"
    chunks = retrieve(query, k=3)

    # Filter out chunks that are off-topic relative to the student's own messages.
    # Without this, a RAG query seeded with a long assistant explanation can pull
    # chunks about adjacent concepts (e.g. "Reversing Strings") that the student
    # never asked about, causing the LLM to pivot to an irrelevant topic.
    #
    # Strategy: collect meaningful words (>4 chars) from student turns in history,
    # then keep only chunks that share at least one word with that vocabulary.
    # If every chunk fails, keep the single highest-scoring one so the LLM still
    # has some curriculum grounding.
    _STOP = {"about", "their", "there", "where", "which", "would", "could", "should",
             "these", "those", "being", "after", "before", "above", "below"}
    student_words = {
        w.lower()
        for w in re.findall(r"[a-zA-Z]{5,}", state["user_input"])
        if w.lower() not in _STOP
    }
    for turn in history:
        if turn.get("role") == "user":
            for w in re.findall(r"[a-zA-Z]{5,}", turn.get("content", "")):
                if w.lower() not in _STOP:
                    student_words.add(w.lower())
    if student_words:
        def _score(chunk: dict) -> int:
            chunk_lower = chunk["text"].lower()
            return sum(1 for w in student_words if w in chunk_lower)
        scores = [(_score(c), c) for c in chunks]
        passing = [c for s, c in scores if s > 0]
        if passing:
            chunks = passing
        elif scores:
            chunks = [max(scores, key=lambda x: x[0])[1]]

    return {"retrieved_chunks": chunks}


def route_intent(
    state: PathwiseState,
) -> Literal["off_topic_handler", "hard_block", "retrieve_context"]:
    """Skip retrieval for off-topic messages and hard blocks (static responses)."""
    if state["intent"] == "off_topic":
        return "off_topic_handler"
    if state["intent"] == "answer_seeking" and state.get("attempt", 1) >= 3:
        return "hard_block"
    return "retrieve_context"


def choose_response(
    state: PathwiseState,
) -> Literal["curriculum_response", "guide_response", "structured_hint"]:
    if state["intent"] == "curriculum":
        # Guard: if history shows 2+ answer-seeking turns, don't use curriculum_response —
        # the student is still fishing for answers with rephrased requests.
        history = state.get("conversation_history") or []
        prior_answer_seeking = sum(
            1 for t in history
            if t.get("role") == "user"
            and any(kw in t.get("content", "").lower() for kw in _ANSWER_SEEKING_KEYWORDS)
        )
        if prior_answer_seeking >= 2:
            return "guide_response"
        return "curriculum_response"
    if state["intent"] == "answer_seeking" and state.get("attempt", 1) == 2:
        return "structured_hint"
    return "guide_response"


# =============================================================================
# Graph
# =============================================================================

def build_graph() -> StateGraph:
    builder = StateGraph(PathwiseState)
    builder.add_node("classify_intent",    classify_intent)
    builder.add_node("retrieve_context",   retrieve_context)
    builder.add_node("curriculum_response", curriculum_response)
    builder.add_node("guide_response",     guide_response)
    builder.add_node("structured_hint",    structured_hint)
    builder.add_node("hard_block",         hard_block)
    builder.add_node("off_topic_handler",  off_topic_handler)

    builder.add_edge(START, "classify_intent")
    builder.add_conditional_edges("classify_intent", route_intent)
    builder.add_conditional_edges("retrieve_context", choose_response)
    builder.add_edge("curriculum_response", END)
    builder.add_edge("guide_response",      END)
    builder.add_edge("structured_hint",     END)
    builder.add_edge("hard_block",          END)
    builder.add_edge("off_topic_handler",   END)
    return builder.compile()
