from groq import Groq
import os
import re

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


# ---------------------------------------------------------------------------
# Answer-leak detection
# ---------------------------------------------------------------------------

_LEAK_PATTERNS = re.compile(
    r"```"                    # triple-backtick code fence
    r"|`[^\s`\n]"             # inline code: `var`, `func()`, `string[:3]`
    r"|the answer is"
    r"|it would return"
    r"|it returns"
    r"|the result is"
    r"|the output is"
    r"|will return"
    r"|will print"
    r"|here'?s the code"
    r"|here is the code",
    re.IGNORECASE,
)

# Softer check for curriculum_response — the function is designed to allow
# illustrative code examples, so only block explicit answer-giveaway phrases,
# not backtick formatting (which the LLM legitimately uses for method names).
_CURRICULUM_LEAK_PATTERNS = re.compile(
    r"the answer is"
    r"|here'?s the (?:full |complete )?(?:answer|solution|code)"
    r"|here is the (?:full |complete )?(?:answer|solution|code)"
    r"|the solution is"
    r"|the correct (?:answer|code) is",
    re.IGNORECASE,
)

# Canned fallbacks used when the LLM leaks an answer despite instructions.
# Kept static so a hallucinating model can't talk its way out of the guardrail.
_GUIDE_FALLBACK = (
    "I can see you're looking for a direct answer, but let's work through this together. "
    "Look back at the relevant section in your lesson material and try to identify "
    "the specific concept that applies here. "
    "What have you tried so far, and where exactly are you getting stuck?"
)

_HINT_FALLBACK = (
    "I know this feels frustrating — let's slow down and break it into the smallest possible step. "
    "Focus on the single concept from your lesson that relates to this problem. "
    "Try writing out, in plain English (not code), what you think that concept does. "
    "Once you can describe it, translating it to code becomes much easier."
)

_CURRICULUM_FALLBACK = (
    "Let's break this down. Look at the relevant section in your lesson material and find the concept that applies here. "
    "Try to describe in plain English — no code yet — what that concept does and how it works. "
    "Once you can explain it in words, what do you think the first step in writing the code would be?"
)


def _leaks_answer(text: str) -> bool:
    """Returns True if the LLM response contains a direct answer or code despite guardrail instructions."""
    return bool(_LEAK_PATTERNS.search(text))


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
        formatted = []
        for c in chunks:
            if isinstance(c, dict):
                meta = ", ".join(filter(None, [c.get("week"), c.get("topic")]))
                header = f"[{meta}]\n" if meta else ""
                formatted.append(f"{header}{c['text']}")
            else:
                formatted.append(c)
        joined = "\n\n".join(formatted)
        parts.append(f"Relevant curriculum material for reference:\n{joined}")
    return "\n\n".join(parts)


def _build_messages(system_prompt: str, state: dict) -> list:
    """
    Builds the full Groq messages list:
      [system] + prior conversation turns (last 6) + current user message.

    Without this, every request is stateless — the LLM sees only the new
    message and has no idea what topic was already being discussed. That caused
    follow-ups like "what do you mean?" to generate responses about completely
    unrelated curriculum concepts.
    """
    messages = [{"role": "system", "content": system_prompt}]
    history = state.get("conversation_history") or []
    for turn in history[-6:]:
        role = turn.get("role", "user")
        # The frontend stores bot messages with role "hint"; Groq requires "assistant".
        if role == "hint":
            role = "assistant"
        messages.append({"role": role, "content": turn.get("content", "")})
    # Current user message goes last so it reads as the active turn.
    messages.append({"role": "user", "content": state["user_input"]})
    return messages


def curriculum_response(state: dict) -> dict:
    """
    Curriculum intent — Substantive, chunk-grounded explanation.

    The student is asking a genuine learning question. The LLM explains the
    relevant concept directly, cites the specific section or method name from
    the retrieved curriculum material, and closes with a check-for-understanding
    question. Short illustrative snippets are allowed; exercise solutions are not.
    """
    client = _groq_client()
    context_block = _build_context_block(state)

    system = (
        "You are Pathwise, a supportive Python learning assistant for a coding bootcamp. "
        "A student has a genuine learning question — answer it clearly and helpfully.\n\n"
    )
    if context_block:
        system += f"{context_block}\n\n"
        system += (
            "Using the curriculum material above as your primary source, answer the student's question. "
            "Name the specific concept, method, or section from the material that applies "
            "(e.g. 'The split() method' or 'As the lesson covers under string methods...'). "
        )
    system += (
        "If the student is asking WHERE to find the material (e.g. 'where in my documents', "
        "'which section', 'which lesson', 'where can I find this'), do NOT explain the concept — "
        "instead cite the specific week and topic from the curriculum material above and direct them there. "
        "Skip any code example in that case.\n\n"
        "Otherwise, explain the concept clearly in 3-5 sentences. "
        "If you include a code example, use DIFFERENT values than those in the exercise — "
        "never use the exact variable names, strings, or numbers from the student's current question. "
        "Do NOT write the solution to the exercise. "
        "End with one question that checks whether the student understood the key point."
    )

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=_build_messages(system, state),
    )
    text = response.choices[0].message.content or ""
    if bool(_CURRICULUM_LEAK_PATTERNS.search(text)):
        return {"response_text": _CURRICULUM_FALLBACK}
    return {"response_text": text}


def guide_response(state: dict) -> dict:
    """
    Attempt 1 — Coaching mode for answer-seeking students.

    The LLM identifies the specific concept from the retrieved curriculum
    material the student needs, asks what they've tried with that concept,
    and points them back to the lesson — without writing code or giving the answer.
    """
    client = _groq_client()
    context_block = _build_context_block(state)

    system = (
        "You are Pathwise, a supportive Python learning assistant for a coding bootcamp. "
        "Your absolute rule: NEVER give direct answers, write code, or reveal solutions. "
        "Your goal is to help students think, not to think for them.\n\n"
    )
    if context_block:
        system += f"{context_block}\n\n"
        system += (
            "The curriculum material above contains exactly the concept this student needs. "
            "Identify and name that specific concept or method (e.g. 'split()', 'string slicing', 'indexing'). "
        )
    system += (
        "IMPORTANT: Use the conversation history to understand what topic the student is referring to — "
        "especially if their message is a follow-up like 'what do you mean?' or 'can you explain that?'. "
        "Respond in 3-4 sentences. "
        "First, name the specific concept from the material they should focus on. "
        "Then ask one targeted question about what they have already tried with that concept. "
        "Finally, tell them which part of the lesson to review — do NOT explain how to apply it."
    )

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=_build_messages(system, state),
    )
    # message.content is typed str | None by the SDK; treat None as empty.
    text = response.choices[0].message.content or ""
    # Small models sometimes ignore the "no direct answers" rule under pressure.
    # If the response leaks an answer or code, swap in the canned fallback.
    if _leaks_answer(text):
        return {"response_text": _GUIDE_FALLBACK}
    return {"response_text": text}


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

    system = (
        "You are Pathwise, a Python learning assistant. This is the student's second request "
        "for help on a similar topic, so they need more structured guidance — but still NO direct answers.\n\n"
    )
    if context_block:
        system += f"{context_block}\n\n"
    system += (
        "IMPORTANT: Use the conversation history to stay on the topic already being discussed. "
        "Do not introduce a new concept unless the conversation history clearly shows the topic shifted.\n\n"
        "Follow this structure in your response:\n"
        "1. Name the key concept they need (draw from the conversation and material above).\n"
        "2. Explain that concept in 1-2 plain-English sentences.\n"
        "3. Give a SHORT analogous example using DIFFERENT values than the student's question.\n"
        "4. End with a guiding question that nudges them toward solving their own problem."
    )

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=_build_messages(system, state),
    )
    text = response.choices[0].message.content or ""
    if _leaks_answer(text):
        return {"response_text": _HINT_FALLBACK}
    return {"response_text": text}


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
