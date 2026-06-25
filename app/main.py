import os
import re
import sys
from typing import Literal, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

# Prefer environment variables already injected by the runtime. For local
# development, load a repo-root .env file if it exists.
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path, override=False)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from guardrails.no_direct_answers import curriculum_response, guide_response, hard_block, structured_hint
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

# Minimum vector-search relevance score a chunk must clear to count as real
# grounding. Calibrated against the live index: genuine in-corpus hits score
# ~0.66–0.76 while out-of-corpus nearest-neighbors top out around ~0.56, so 0.60
# sits cleanly in the gap. Below this we treat the question as having NO
# curriculum match and return nothing, rather than feeding the LLM an irrelevant
# chunk it will fabricate a citation around. Tune up if hallucinated grounding
# persists, down if legitimate questions start coming back ungrounded.
MIN_RELEVANCE_SCORE = 0.60

_ANSWER_SEEKING_KEYWORDS = [
    # Direct answer demands
    "what is the answer", "give me the answer", "tell me the answer",
    "i want the answer", "want the answer", "i need the answer", "need the answer",
    "give me an answer", "just need the answer", "can i have the answer",
    "just have the answer", "just tell me", "just give me",
    "what's the answer", "whats the answer", "tell me what it is",
    "can you just tell me", "please just tell me", "i just want to know the answer",
    "what's the right answer", "what is the correct answer", "give me the right answer",
    "answer this for me", "just answer it", "answer the question",

    # Solution requests
    "what's the solution", "what is the solution", "solve this for me",
    "show me the solution", "give me the solution", "answer is",
    "what's the correct solution", "what is the correct solution",
    "what should the solution be", "just solve it", "solve it for me",
    "can you solve this", "how do you solve this", "solve this problem for me",
    "what's the final answer", "final answer is", "what does the answer look like",

    # Code generation requests
    "write the code", "write me the code", "give me the code",
    "just code it", "code it for me", "can you code this for me", "can i have the code",
    "write this code for me", "write me a solution", "write the solution",
    "code this for me", "give me a working solution", "give me the full code",
    "give me the complete code", "write the full solution", "just write it for me",
    "can you write this for me", "write a program that", "give me a program that",
    "implement this for me", "just implement it", "make it work for me",
    "complete this code", "finish this code for me", "fill in the code",
    "write the function", "write the class",

    # What to write
    "what should i write", "what do i write", "what should i type",
    "what do i type here", "what goes here", "what should go here",
    "what do i put here", "what should i put", "tell me what to write",
    "tell me what to type", "what should the code say",
    "what should the function look like", "what should i return", "what should i output",

    # Do it for me
    "do it for me", "just do it for me", "can you do this for me",
    "do this for me", "please do it for me", "you do it", "you do it for me",
    "just do it", "can you just do it", "handle this for me",
    "take care of it for me", "figure it out for me",

    # Just show / reveal
    "just show me", "can you just give", "show me how it's done",
    "show me the answer", "show me the code", "just show me the result",
    "show me what it should look like", "reveal the answer", "just reveal it",
    "show me the working", "show me the output",

    # Completed work
    "give me the completed version", "give me the finished code",
    "give me the working code", "give me a finished solution",
    "give me the full solution", "what does the final code look like",
    "what does the completed code look like", "what is the finished program",
    "paste the answer", "paste the solution", "paste the code", 
]

_OFF_TOPIC_KEYWORDS = [
    # Entertainment & media
    "movie", "music", "game", "podcast", "streaming", "concert", "festival",
    "youtube", "tiktok", "meme", "viral", "influencer", "celebrity",
    "tv show", "netflix", "anime", "video game", "trailer", "box office",
    "album", "playlist", "twitch", "instagram", "reddit", "fan fiction", "comic book",

    # News & current events
    "news", "politics", "election", "war", "lawsuit", "conspiracy",
    "breaking news", "headline", "protest", "government", "president",
    "congress", "senate", "supreme court", "bill passed", "scandal", "impeachment",

    # Finance
    "stock", "crypto", "mortgage", "insurance", "taxes", "lottery", "gambling",
    "bitcoin", "investing", "real estate", "interest rate", "credit score",
    "401k", "nft", "hedge fund", "forex", "day trading",

    # Sports
    "sports", "nfl", "nba", "mlb", "soccer", "football", "basketball",
    "baseball", "tennis", "golf", "olympics", "world cup", "fantasy sports",
    "scores", "standings",

    # Lifestyle & wellness
    "recipe", "fitness", "diet", "fashion", "travel", "shopping", "coupon",
    "gardening", "diy", "workout", "nutrition", "weight loss", "meal prep",
    "skincare", "makeup", "home decor", "interior design", "cleaning tips",
    "vacation", "hotel", "flight deals",

    # Relationships & social
    "dating", "relationship", "parenting", "social media", "pets",
    "breakup", "divorce", "marriage", "friendship", "family drama",
    "tinder", "online dating", "cheating", "hurt", "pain", "depressed",

    # Beliefs & spirituality
    "religion", "astrology", "horoscope", "zodiac", "tarot", "psychic",
    "manifestation", "meditation", "prayer", "church", "spiritual",

    # Transportation & home
    "car", "truck", "suv", "motorcycle", "used car", "car repair", "oil change",
    "home improvement", "plumbing", "electrician", "roof repair", "lawn care",

    # Weather
    "weather", "forecast", "hurricane", "tornado", "snow day", "temperature outside",
]


# Matches any Latin-script letter (covers accented chars like é/ñ so legitimately
# punctuated English questions aren't misread as having no letters). Used to
# distinguish real curriculum questions from emoji/non-Latin/symbol-only input.
_LATIN_LETTER = re.compile(r"[A-Za-zÀ-ɏ]")


def _has_latin_content(text: str) -> bool:
    """True if the message contains at least one Latin-script letter."""
    return bool(_LATIN_LETTER.search(text))


def classify_intent(state: PathwiseState) -> dict:
    """Routes the student message to one of three intents."""
    raw = state["user_input"]
    text = raw.lower()
    if not _has_latin_content(raw):
        # The curriculum is an English-language Python bootcamp, so a real
        # learning question always contains Latin-script letters. A message with
        # none — emoji-only ("🔥💀🌈"), a non-Latin script ("हाय आप कैसे हैं"),
        # or pure punctuation/symbols — cannot be a curriculum question. Without
        # this guard such inputs fall through to the curriculum default below and
        # get sent to the LLM, which dutifully answers them (even replying in the
        # student's language). Route them to the static off_topic handler so they
        # never reach the model.
        intent = "off_topic"
    elif any(kw in text for kw in _ANSWER_SEEKING_KEYWORDS):
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

    # Relevance gate (vector-search score). The index always returns k nearest
    # neighbors, even when the student asks about something not in the corpus
    # (e.g. recursion while only week_01 strings is loaded) — those come back at
    # a low score. Dropping sub-threshold chunks here means an out-of-corpus
    # question yields no grounding at all, so the response nodes answer honestly
    # instead of inventing a curriculum citation. This runs BEFORE the keyword
    # filter below so weak matches can't be resurrected as the "best" chunk.
    chunks = [c for c in chunks if (c.get("score") or 0) >= MIN_RELEVANCE_SCORE]

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
