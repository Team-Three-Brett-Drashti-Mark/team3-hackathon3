from typing import TypedDict, Literal
from langgraph.graph import END, START, StateGraph
from dotenv import load_dotenv
import os

# Load environment variables from .env (works from any working directory)
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(_env_path)

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from guardrails.no_direct_answers import guide_response, structured_hint, hard_block
from retrieval.retriever import retrieve


# =============================================================================
# State
# =============================================================================

class PathwiseState(TypedDict):
    user_input: str         # Raw message from the student
    lesson_context: str     # Problem/exercise text the student is working on
    retrieved_chunks: list  # Relevant curriculum chunks from vector search
    intent: str             # "answer_seeking" | "curriculum" | "off_topic"
    attempt: int            # Guardrail escalation counter (1 → 2 → 3)
    response_text: str      # Final response sent back to the student


# =============================================================================
# Classifier & Router Nodes
# =============================================================================

_ANSWER_SEEKING_KEYWORDS = [
    "what is the answer", "give me the answer", "just tell me",
    "what's the solution", "what is the solution", "solve this for me",
    "write the code", "write me the code", "do it for me", "show me the solution",
    "answer is", "what should i write", "what do i write", "give me the code",
]

_OFF_TOPIC_KEYWORDS = [
    "weather", "sports", "news", "movie", "music", "game", "recipe",
    "politics", "stock", "crypto", "dating",
]


def classify_intent(state: PathwiseState) -> dict:
    """Routes the student message to one of three intents."""
    text = state["user_input"].lower()
    if any(kw in text for kw in _ANSWER_SEEKING_KEYWORDS):
        return {"intent": "answer_seeking"}
    if any(kw in text for kw in _OFF_TOPIC_KEYWORDS):
        return {"intent": "off_topic"}
    return {"intent": "curriculum"}


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
    # Combine the lesson context with the student's question for a richer query
    query = state["user_input"]
    if state.get("lesson_context"):
        query = f"{state['lesson_context']}\n{state['user_input']}"
    chunks = retrieve(query, k=3)
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
) -> Literal["guide_response", "structured_hint"]:
    if state["intent"] == "answer_seeking" and state.get("attempt", 1) == 2:
        return "structured_hint"
    return "guide_response"


# =============================================================================
# Graph
# =============================================================================

def build_graph() -> StateGraph:
    builder = StateGraph(PathwiseState)
    builder.add_node("classify_intent",   classify_intent)
    builder.add_node("retrieve_context",  retrieve_context)
    builder.add_node("guide_response",    guide_response)
    builder.add_node("structured_hint",   structured_hint)
    builder.add_node("hard_block",        hard_block)
    builder.add_node("off_topic_handler", off_topic_handler)

    builder.add_edge(START, "classify_intent")
    builder.add_conditional_edges("classify_intent", route_intent)
    builder.add_conditional_edges("retrieve_context", choose_response)
    builder.add_edge("guide_response",    END)
    builder.add_edge("structured_hint",   END)
    builder.add_edge("hard_block",        END)
    builder.add_edge("off_topic_handler", END)
    return builder.compile()
