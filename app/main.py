from typing import TypedDict, Literal
from langgraph.graph import END, START, StateGraph
from dotenv import load_dotenv
import os

# Load GROQ_API_KEY from .env (works from any working directory)
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(_env_path)

# Also load guardrails from the sibling package
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from guardrails.no_direct_answers import guide_response, structured_hint, hard_block


# =============================================================================
# State
# =============================================================================

class PathwiseState(TypedDict):
    user_input: str       # Raw message from the student
    intent: str           # "answer_seeking" | "curriculum" | "off_topic"
    attempt: int          # Guardrail escalation counter (1 → 2 → 3)
    response_text: str    # Final response sent back to the student


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


def off_topic_handler(state: PathwiseState) -> dict:
    return {
        "response_text": (
            "I'm Pathwise, your Python learning assistant! "
            "I can only help with questions related to your curriculum and course material. "
            "Feel free to ask me about Python concepts, your assignments, or anything in the lesson panel. 📖"
        )
    }


def choose_path(
    state: PathwiseState,
) -> Literal["guide_response", "structured_hint", "hard_block", "off_topic_handler"]:
    """Conditional edge: pick next node based on intent and attempt count."""
    if state["intent"] == "off_topic":
        return "off_topic_handler"
    if state["intent"] == "curriculum":
        return "guide_response"
    # answer_seeking — escalate
    attempt = state.get("attempt", 1)
    if attempt >= 3:
        return "hard_block"
    elif attempt == 2:
        return "structured_hint"
    return "guide_response"


# =============================================================================
# Graph
# =============================================================================

def build_graph() -> StateGraph:
    builder = StateGraph(PathwiseState)
    builder.add_node("classify_intent",   classify_intent)
    builder.add_node("guide_response",    guide_response)
    builder.add_node("structured_hint",   structured_hint)
    builder.add_node("hard_block",        hard_block)
    builder.add_node("off_topic_handler", off_topic_handler)
    builder.add_edge(START, "classify_intent")
    builder.add_conditional_edges("classify_intent", choose_path)
    builder.add_edge("guide_response",    END)
    builder.add_edge("structured_hint",   END)
    builder.add_edge("hard_block",        END)
    builder.add_edge("off_topic_handler", END)
    return builder.compile()
