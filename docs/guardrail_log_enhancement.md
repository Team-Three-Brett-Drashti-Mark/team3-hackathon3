# Off-Topic Guardrail Bypass: Non-English and Emoji-Only Messages

## What I Found

While digging through the interaction logs, I noticed some messages that clearly should not have reached the model at all, but were getting full LLM-generated responses anyway. Here are two examples pulled straight from the logs:

**Example 1**

> Student: हाय आप कैसे हैं
>
> Pathwise: नमस्ते! मैं ठीक हूं, धन्यवाद! आप पाइथन से संबंधित कोई सवाल पूछना चाहते हैं या किसी विशिष्ट विषय पर मदद करना चाहते हैं?

**Example 2**

> Student: 🔥💀🌈
>
> Pathwise: Seems like you're expressing some creativity and flair. Unfortunately, I'm a Python learning assistant, so I'll stick to helping with coding-related topics. Would you like to work on a Python exercise or have a question about a specific topic?

Both of these were tagged with the `curriculum` intent in the logs, which means they went through retrieval and hit the LLM. Neither one should have. The first message is Hindi small talk, and the assistant actually replied back in Hindi, which is not something this bot is supposed to do. The second is just three emoji with no real content at all. Both should have been caught by the off-topic guardrail and answered with the static, canned response instead.

## Digging Into Why This Was Happening

I traced the routing logic back to `classify_intent` in `app/main.py`. The classifier decides where a message goes using two keyword lists, and the logic looks like this:

```python
if any(kw in text for kw in _ANSWER_SEEKING_KEYWORDS):
    intent = "answer_seeking"
elif any(kw in text for kw in _OFF_TOPIC_KEYWORDS):
    intent = "off_topic"
else:
    intent = "curriculum"   # default for anything unmatched
```

The off-topic list is just a denylist of English words like "weather" and "sports." That is the problem right there. A denylist of English words has no way of matching text that is not in English, or text that has no words in it at all. So if a message does not happen to contain one of those flagged English terms, it falls through to the `else` branch and gets labeled `curriculum` by default, which sends it straight into the LLM pipeline.

Emoji-only input and non-Latin-script input both have zero matchable English tokens, so they were guaranteed to fall into that default every single time. That explains exactly what I was seeing in the logs.

## The Fix

Since this is meant to be an English-language Python bootcamp assistant, my fix was to add a check at the very top of the classifier: a real learning question should contain at least one Latin-script letter. If a message has none, it gets routed directly to the existing static `off_topic_handler`, which just returns a canned redirect and never touches the LLM or the vector search.

Here is the helper I added to detect Latin-script content:

```python
_LATIN_LETTER = re.compile(r"[A-Za-zÀ-ɏ]")

def _has_latin_content(text: str) -> bool:
    """True if the message contains at least one Latin-script letter."""
    return bool(_LATIN_LETTER.search(text))
```

And here is the updated classifier with that check added first:

```python
if not _has_latin_content(raw):
    intent = "off_topic"
elif any(kw in text for kw in _ANSWER_SEEKING_KEYWORDS):
    intent = "answer_seeking"
elif any(kw in text for kw in _OFF_TOPIC_KEYWORDS):
    intent = "off_topic"
else:
    intent = "curriculum"
```

This one check covers a lot of ground at once. It catches emoji-only messages, non-Latin scripts, punctuation-only input, and digit-only input, all in a single pass. I included the accented character range (À-ɏ) on purpose, so that legitimate English text with accented characters does not get mistakenly flagged as having no letters at all. And anything with mixed scripts that still contains a real Latin word, something like `print()` sitting next to other characters, still classifies normally and is not affected.

## How I Tested It

I checked this at three different levels before calling it done.

**Unit tests.** I added new cases to `tests/test_classifier.py` covering emoji-only input, Devanagari script, Han script, punctuation-only input, digit-only input, and empty input. All of those are expected to come back as `off_topic`. I also added a mixed-script case that includes a real Latin word, which is expected to still classify as `curriculum`.

**End-to-end run.** I ran both of the original logged inputs through the fully compiled LangGraph, with the LLM node and the retrieval function patched as tripwires so I would know immediately if either one got called. Both messages came back as `off_topic` with the static response, and the LLM was invoked zero times.

**Regression check.** I ran the full classifier, guardrail, and graph-integration suites, and all 82 tests pass. The only failures in the broader test run are pre-existing ones in the logger and retriever modules that are unrelated to this change, and they fail the exact same way without my fix applied, so I'm confident I did not break anything else.

## Result

Emoji-only and non-Latin-script messages are now correctly caught as off-topic and answered with the static redirect, without ever reaching the LLM. Legitimate Python questions are unaffected by this change.

## Known Limitation

This fix gates strictly on Latin script. That means a genuine Python question typed entirely in another script would still get flagged as off-topic, since the check has no way to tell the difference between "off-topic in another language" and "a real question in another language." That said, this matches how the system is currently designed, since it is meant to support English-only learners for now. If support for non-English learners becomes a goal down the line, that would need an actual language-detection step rather than a simple script check like this one.