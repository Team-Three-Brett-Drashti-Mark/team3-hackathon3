from groq import Groq
import os

# ---------------------------------------------------------------------------
# Guardrail Response Nodes
# ---------------------------------------------------------------------------
# Each function is a LangGraph node that receives PathwiseState and returns
# a partial state update (just response_text).
#
# Escalation path:
#   Attempt 1 → guide_response    (coaching mode — "what have you tried?")
#   Attempt 2 → structured_hint   (concept reminder + analogous example)
#   Attempt 3 → hard_block        (static redirect — no LLM call)
# ---------------------------------------------------------------------------


def _groq_client() -> Groq:
    """Returns a Groq client, raising clearly if the key is missing."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set. Add it to your .env file.")
    return Groq(api_key=api_key)


def _build_context_block(state: dict) -> str:
    """Assembles lesson context and retrieved curriculum chunks into a prompt block."""
    parts = []
    if state.get("lesson_context"):
        parts.append(f"The student is currently working on this exercise:\n{state['lesson_context']}")
    chunks = state.get("retrieved_chunks") or []
    if chunks:
        joined = "\n\n".join(chunks)
        parts.append(f"Relevant curriculum material for reference:\n{joined}")
    return "\n\n".join(parts)


def guide_response(state: dict) -> dict:
    """
    Attempt 1 — Friendly coaching mode.

    The LLM is instructed to ask what the student has tried, point to the
    relevant concept, and encourage — without ever writing code or revealing
    the answer. Lesson context and retrieved curriculum chunks are injected
    so responses are grounded in the student's actual exercise.
    """
    client = _groq_client()
    context_block = _build_context_block(state)

    prompt = (
        "You are Pathwise, a supportive Python learning assistant for a coding bootcamp. "
        "Your absolute rule: NEVER give direct answers, write code, or reveal solutions. "
        "Your goal is to help students think, not to think for them.\n\n"
    )
    if context_block:
        prompt += f"{context_block}\n\n"
    prompt += (
        "Respond in 2-4 sentences. Start by acknowledging the question warmly, "
        "then ask what the student has already tried, and hint at the relevant concept "
        "from the material above they should explore — without spelling out how to apply it.\n\n"
        f"Student question: {state['user_input']}"
    )

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
    )
    return {"response_text": response.choices[0].message.content}


def structured_hint(state: dict) -> dict:
    """
    Attempt 2 — Structured concept reminder.

    The student has asked more than once. The LLM names the concept,
    explains it briefly, gives an analogous (but different) code example,
    and ends with a guiding question — still no direct answer. Grounded
    in the student's lesson context and retrieved curriculum chunks.
    """
    client = _groq_client()
    context_block = _build_context_block(state)

    prompt = (
        "You are Pathwise, a Python learning assistant. This is the student's second request "
        "for help on a similar topic, so they need more structured guidance — but still NO direct answers.\n\n"
    )
    if context_block:
        prompt += f"{context_block}\n\n"
    prompt += (
        "Follow this structure in your response:\n"
        "1. Name the key concept they need (draw from the material above if relevant).\n"
        "2. Explain that concept in 1-2 plain-English sentences.\n"
        "3. Give a SHORT analogous example using DIFFERENT values than the student's question.\n"
        "4. End with a guiding question that nudges them toward solving their own problem.\n\n"
        f"Student question: {state['user_input']}"
    )

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
    )
    return {"response_text": response.choices[0].message.content}


def hard_block(_state: dict) -> dict:
    """
    Attempt 3 — Hard block. No LLM call.

    After three answer-seeking attempts the student is redirected to
    conceptual review and their instructor. No further hints.
    """
    return {
        "response_text": (
            "🚫 It looks like you've asked for a direct answer several times now.\n\n"
            "Pathwise is designed so you build real understanding — giving you the solution "
            "would shortcut that process.\n\n"
            "Here's what I'd suggest:\n"
            "  • Re-read the lesson panel on this topic.\n"
            "  • Break the problem into the smallest possible piece and tackle just that.\n"
            "  • If you're genuinely stuck, flag your instructor for a 1-on-1 session.\n\n"
            "You've got this — come back once you've had a chance to review the material. 💪"
        )
    }
