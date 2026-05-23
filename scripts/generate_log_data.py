"""
Generates ~200 rows of synthetic interaction data for capstone.logging.interaction_logs.

Story: ~40 student sessions on the Pathwise Python strings unit.
  - 25 healthy sessions  (curriculum-dominant, engaged learners)
  - 10 at-risk sessions  (escalating answer_seeking, attempt 1→2→3)
  -  5 off-topic sessions (disengaged, 1-2 turns then dropped)

Run with:
  uv run --python 3.12 --with "databricks-connect>=16.4,<17.4" --with faker \
         scripts/generate_log_data.py
"""

import os
import uuid
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Load env vars from project .env
env_path = Path(__file__).parent.parent / ".env"
for line in env_path.read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip("'\""))

from databricks.connect import DatabricksSession  # noqa: E402
import pandas as pd                              # noqa: E402
from pyspark.sql.types import (                  # noqa: E402
    StructType, StructField, StringType, TimestampType, IntegerType,
)

random.seed(42)

# ---------------------------------------------------------------------------
# Content pools — realistic Python tutor interactions
# ---------------------------------------------------------------------------

CURRICULUM_INPUTS = [
    "What does the slice s[0:3] mean exactly?",
    "How do I get the last 3 characters of a string?",
    "Can you explain how s[::2] works?",
    "What's the difference between .upper() and .lower()?",
    "How does len() count characters in a string?",
    "What does .strip() do and when would I use it?",
    "I'm confused about negative indexing like s[-1]",
    "How does .split() work? What does it return?",
    "What is .find() and what does it return if not found?",
    "Can you explain .replace() with an example?",
    "What does .startswith() return — True/False or the substring?",
    "How do I join a list of words into a single string?",
    "What's the difference between s[1:] and s[1:len(s)]?",
    "Why does s[0:3] give me 3 characters and not 4?",
    "What happens if my slice index is out of range?",
    "How do I reverse a string using slicing?",
    "Does .upper() change the original string or return a new one?",
    "What does immutable mean for strings in Python?",
    "I tried to change one character of a string and got a TypeError?",
    "What is the step parameter in slicing like s[::2]?",
    "How do I check if a substring is inside a string?",
    "What's the difference between .count() and len()?",
    "Can I slice with only a start or only an end index?",
    "How do I convert a string to a list of characters?",
    "What does s[::-1] do?",
]

ANSWER_SEEKING_INPUTS = [
    "Just give me the answer",
    "What is the answer to this question?",
    "Can you just write the code for me?",
    "Tell me the solution please",
    "I just need the answer, not a hint",
    "Give me the code and I'll understand it later",
    "Just tell me what to type",
    "What should I write here?",
    "I want the answer",
    "Can you just solve this for me?",
    "What do I write?",
    "Just need the answer real quick",
    "Give me the solution",
    "I need the answer now",
    "Can I just have the answer?",
]

OFF_TOPIC_INPUTS = [
    "What's the weather like today?",
    "Can you recommend a good movie?",
    "What's the score of the game last night?",
    "Tell me a joke",
    "What stocks should I buy?",
    "Who won the election?",
    "Can you help me with my taxes?",
    "What's a good recipe for pasta?",
    "What's my horoscope today?",
    "Who's the best basketball player right now?",
]

CURRICULUM_OUTPUTS = [
    "Think about what the index numbers represent. In Python, indexing starts at 0, so the first character is at position 0. Given that, what do you think s[0:3] would select? Try tracing through it character by character.",
    "Great question about negative indexing! Python lets you count from the end of a string using negative numbers. So s[-1] gives you the last character, s[-2] gives the second-to-last. Can you figure out what s[-3:] would give you for 'cheese'?",
    "String slicing follows the pattern s[start:end:step]. The step controls how you move through the string — a step of 2 means take every other character. If your string is 'hello', what do you think s[::2] would return?",
    "Good observation! The .upper() method returns a *new* string in all caps — it doesn't change the original. This is because strings in Python are immutable. Can you think of a way to verify that by printing both the original and the result?",
    "len() counts every character in the string, including spaces and punctuation. So len('hello') is 5 and len('hello world') is 11. What do you think len('') would return for an empty string?",
    "The .strip() method removes whitespace from both ends of a string. It's really useful for cleaning up user input. What would '  hello  '.strip() return?",
    ".split() breaks a string into a list using a delimiter. By default it splits on whitespace. So 'hello world'.split() gives ['hello', 'world']. What would 'a,b,c'.split(',') return?",
    ".find() returns the index of the first occurrence of a substring, or -1 if it's not found. So 'hello'.find('e') returns 1. What would 'hello'.find('z') return?",
    "Slicing in Python doesn't raise an error if your indices go out of range — it just gives you what it can. So s[0:100] on a 5-character string returns the whole string. Try it and see!",
    "The .join() method is called on a separator string and takes an iterable. So ', '.join(['a', 'b', 'c']) gives 'a, b, c'. How might you join a list of words with a single space?",
    "Immutable means you can't change a string in place. If you try s[0] = 'X', Python raises a TypeError. But you *can* create a new string by concatenating or slicing. Does that distinction make sense?",
    "The step in slicing controls the stride. s[::2] means start at the beginning, go to the end, take every 2nd character. What would s[1::2] give you — even-indexed or odd-indexed characters?",
    "Good instinct! s[1:] and s[1:len(s)] give the same result because the slice end defaults to the length when omitted. They're equivalent — which one looks cleaner to you?",
    "The 'in' keyword checks for substring membership. So 'ell' in 'hello' returns True. Can you figure out how to check if a string contains any vowel?",
    "s[::-1] starts at the end, goes to the beginning, stepping backward — it's the Pythonic way to reverse a string. Try it with 'python' and see what you get!",
]

ANSWER_SEEKING_OUT_1 = [
    "I can see you're looking for the answer, but my role is to help you discover it yourself! What do you already know about string indexing in Python? Even a partial understanding gives us a starting point.",
    "I get it — sometimes you just want the answer. But working through it yourself is what makes it stick. Tell me: what part of the problem feels most confusing right now?",
    "My job is to guide you, not hand over answers — but that doesn't mean I can't help! Tell me where you're stuck and we'll work through it together. What have you tried so far?",
    "I understand the urge to skip ahead! But the hint approach will help you much more in the long run. What does the question ask you to do? Let's break it into smaller pieces.",
    "Rather than giving you the answer directly, let me point you in the right direction: the question is testing your understanding of string indexing. Do you remember how Python counts positions — starting from 0 or 1?",
]

ANSWER_SEEKING_OUT_2 = [
    "I see you're still looking for the direct answer — I understand the pressure! Here's a structured hint: for string slicing, think about s[start:end]. The result includes the character at 'start' but NOT the one at 'end'. Does that help narrow it down?",
    "Let me give you a more concrete hint. Python string indices start at 0. So for 'cheese': c=0, h=1, e=2, e=3, s=4, e=5. Now can you work out the slice that gives you the first three characters?",
    "Okay, let me be more direct. The .upper() method returns the same string but all caps — it needs no arguments, just call it on your string with parentheses. Does that unlock it for you?",
    "Here's a concrete stepping stone: len() takes one argument (your string) and returns an integer — len('hello') is 5, len('') is 0. Can you apply that to the string in the question now?",
    "Let me break this down more explicitly. You need slice notation: string[start:end]. For the first 3 characters, start is 0 (or omit it) and end is 3. The end index is exclusive. Can you put that together?",
]

ANSWER_SEEKING_OUT_3 = [
    "You've asked for the direct answer three times now, so I need to pause here. I'm not able to give you the solution — that's a core rule of how I work. I'd encourage you to re-read the lesson panel, try something in the code editor even if it's wrong, and come back with a specific question about *why* something didn't work. You're closer than you think!",
    "This is your third attempt to get the direct answer, and I want to be honest: continuing to ask won't change my response. What I *can* do is tell you that all the information you need is in the lesson panel. Read the slicing examples carefully, try one of them, and ask me about what confused you. I believe you can get there.",
    "At this point I'm going to ask you to take a different approach. Close the chat for a moment, re-read the lesson, and type *something* in the code editor — even a guess. Getting it wrong is a completely valid step. Come back and tell me what you tried and what happened, and we'll go from there.",
]

OFF_TOPIC_OUTPUT = (
    "I'm Pathwise, your Python learning assistant! "
    "I can only help with questions related to your curriculum and course material. "
    "Feel free to ask me about Python concepts, your assignments, or anything in the lesson panel."
)

# ---------------------------------------------------------------------------
# Generate rows
# ---------------------------------------------------------------------------

END_DATE = datetime.now(timezone.utc)
START_DATE = END_DATE - timedelta(days=30)

# Hour-of-day weights: skewed toward evening (19:00–22:00 UTC)
HOUR_WEIGHTS = [1,1,1,1,1,1,1,1,2,2,3,3,3,4,4,5,5,6,8,10,10,9,7,3]


def rand_timestamp() -> datetime:
    day_offset = random.randint(0, 30)
    hour = random.choices(range(24), weights=HOUR_WEIGHTS, k=1)[0]
    return (START_DATE + timedelta(days=day_offset)).replace(
        hour=hour,
        minute=random.randint(0, 59),
        second=random.randint(0, 59),
        microsecond=0,
    )


rows: list[dict] = []


def add_row(session_id, ts, user_in, sys_out, intent, attempt):
    rows.append({
        "log_id":               str(uuid.uuid4()),
        "session_id":           session_id,
        "timestamp":            ts,
        "user_input":           user_in,
        "system_output":        sys_out,
        "intent":               intent,
        "attempt":              attempt,
        "input_length_chars":   len(user_in),
        "response_length_chars": len(sys_out),
    })


# 25 healthy sessions — curriculum-dominant
for _ in range(25):
    sid = str(uuid.uuid4())
    base = rand_timestamp()
    for turn in range(random.randint(2, 6)):
        ts = base + timedelta(minutes=turn * random.randint(1, 4))
        user_in = random.choice(CURRICULUM_INPUTS)
        sys_out = random.choice(CURRICULUM_OUTPUTS)
        add_row(sid, ts, user_in, sys_out, "curriculum", 1)

# 10 at-risk sessions — escalating answer_seeking (attempt 1→2→3)
for _ in range(10):
    sid = str(uuid.uuid4())
    base = rand_timestamp()
    offset = 0

    # 1-2 legit questions to start
    for _ in range(random.randint(1, 2)):
        ts = base + timedelta(minutes=offset * random.randint(1, 3))
        add_row(sid, ts, random.choice(CURRICULUM_INPUTS),
                random.choice(CURRICULUM_OUTPUTS), "curriculum", 1)
        offset += 1

    # Escalation: 1 → 2 → 3
    for attempt, pool in enumerate([ANSWER_SEEKING_OUT_1,
                                     ANSWER_SEEKING_OUT_2,
                                     ANSWER_SEEKING_OUT_3], start=1):
        ts = base + timedelta(minutes=offset * random.randint(1, 3))
        add_row(sid, ts, random.choice(ANSWER_SEEKING_INPUTS),
                random.choice(pool), "answer_seeking", attempt)
        offset += 1

# 5 off-topic sessions — 1-2 turns then disengaged
for _ in range(5):
    sid = str(uuid.uuid4())
    base = rand_timestamp()
    for turn in range(random.randint(1, 2)):
        ts = base + timedelta(minutes=turn * 2)
        add_row(sid, ts, random.choice(OFF_TOPIC_INPUTS),
                OFF_TOPIC_OUTPUT, "off_topic", 1)

print(f"Generated {len(rows)} rows across 40 sessions")

# ---------------------------------------------------------------------------
# Write to Delta via Databricks Connect (serverless)
# ---------------------------------------------------------------------------

spark = DatabricksSession.builder.serverless(True).getOrCreate()

schema = StructType([
    StructField("log_id",                StringType(),    False),
    StructField("session_id",            StringType(),    False),
    StructField("timestamp",             TimestampType(), False),
    StructField("user_input",            StringType(),    False),
    StructField("system_output",         StringType(),    False),
    StructField("intent",                StringType(),    False),
    StructField("attempt",               IntegerType(),   False),
    StructField("input_length_chars",    IntegerType(),   False),
    StructField("response_length_chars", IntegerType(),   False),
])

sdf = spark.createDataFrame(pd.DataFrame(rows), schema=schema)
sdf.write.mode("append").saveAsTable("capstone.logging.interaction_logs")

print(f"Done — {len(rows)} rows written to capstone.logging.interaction_logs")
