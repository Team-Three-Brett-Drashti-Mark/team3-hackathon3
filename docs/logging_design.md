# Logging Design: Session-Based Interaction Tracking

## What we log

Every `/chat` request writes one row to `capstone.logging.interaction_logs`:

| Column | Example | Purpose |
|---|---|---|
| `log_id` | `a3f2...` | Unique row ID (UUID) |
| `session_id` | `b7c1...` | Groups all turns in one question session |
| `timestamp` | `2026-05-23 14:03:11` | UTC time of the interaction |
| `user_input` | `"what is slicing?"` | Raw student message |
| `system_output` | `"Think about index ranges..."` | Full AI response |
| `intent` | `curriculum` | Classified intent |
| `attempt` | `1` | Guardrail escalation counter |
| `input_length_chars` | `22` | Derived metric |
| `response_length_chars` | `341` | Derived metric |

## Identity approach: anonymous session ID

**Decision:** We log a `session_id` (UUID) per question, not a user identity.

**Why not full identity (name/email/user account):**
- Pathwise has no authentication layer yet
- Storing PII without a clear retention + access policy creates liability before it creates value
- Students may be minors depending on the context

**Why not purely per-request (no session grouping):**
- A UUID per request makes it impossible to answer session-level questions: how many turns did a student need before unblocking? What's the escalation rate per session? These are exactly the signals the Phase 2 admin dashboard needs.

**Why per-question session IDs (not per-page-visit):**
- Each question is a distinct learning context — grouping turns within a question is the unit of analysis that matters for the admin dashboard (struggle heatmaps, escalation rates by topic)
- `resetQuestionState()` in `App.jsx` generates a fresh `crypto.randomUUID()` each time the student moves to a new question

**Future path if identity is needed:**
- Add a lightweight login (email only) and store a hashed or opaque `user_id` alongside `session_id`
- The table schema supports adding a `user_id STRING` column without breaking existing rows

## Where logs go

- **Primary:** `capstone.logging.interaction_logs` (Delta table, UC-governed)
- **Fallback:** `app.log` (local flat file) — written only if the Databricks SDK call fails, so no interaction is silently dropped

## Admin views

Three pre-built views in `capstone.logging` for the admin dashboard:

| View | What it answers |
|---|---|
| `v_daily_usage` | Queries per day, unique sessions, avg message length |
| `v_intent_breakdown` | Distribution of curriculum / answer_seeking / off_topic |
| `v_hourly_activity` | Peak usage hours |
