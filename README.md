# Pathwise — Private Learning Assistant

## Problem Statement
Cohort-based learning programs lack a scalable system that can help students learn through guided support without giving direct answers, while also giving instructors and administrators visibility into learning progress and struggles.

## The Solution
We built a private learning assistant that sits directly on top of a program's curriculum.

Instead of just answering questions like a typical chatbot, our system acts as a guide. When students ask questions in natural language, it points them to the right material, asks follow-up questions, and helps them think through the problem without giving the final answer. Meanwhile, instructors and administrators gain deep visibility into what's actually happening: which topics are asked about most, where students get stuck, and which parts of the curriculum are heavily referenced.

## Runtime Modes
Pathwise now supports two ways of running:

* Local development mode for iteration on a laptop or workstation.
* Hosted Databricks Apps deployment for a single hosted web app inside Databricks.

In local development, the project still runs as two processes:

* FastAPI backend on `http://localhost:8000`
* Vite frontend on `http://localhost:5173`

In the hosted Databricks App, the architecture is different:

* `app/api.py` serves the built React frontend from `frontend/dist`
* the frontend calls `/chat` using a relative URL instead of a hardcoded localhost backend
* `app/api.py` also provides static asset serving and SPA fallback routing
* `app/main.py` prefers runtime-injected environment variables and uses `.env` only as a local fallback
* `app/logger.py` writes fallback logging information to stdout as well as `app.log`

## Current Databricks App Status
A Databricks App named `pathwise` has already been deployed from this repo in the current workspace. The deployment source path is the repo root:

`/Workspace/Repos/w.brett.coleman@gmail.com/team3-hackathon3`

The hosted deployment is driven by the repo-root `app.yaml` file.

## Architecture & Pipeline
We designed a robust Bronze, Silver, Gold data pipeline:

* **Bronze Layer:** Raw curriculum ingestion (PDFs, Markdown, text, quizzes, rubrics).
* **Silver Layer:** Processing, cleaning, deduplication, and chunking. Metadata (e.g., week, topic, assignment type) is added to make the data structured and searchable.
* **Gold Layer:** Embeddings are stored in a Databricks Vector Search index connected to a retriever.

*Workflow:* Student queries are intercepted to retrieve the most relevant curriculum first. This is passed through our **Guardrail Layer** which enforces the "no direct answers" rule, before the LLM generates a guided response. System logs feed directly into admin insights.

## Guardrail Philosophy
A core feature of the product is ensuring students *learn* rather than copy-paste solutions. We enforce this through multiple layers (intent detection, policy engine, retrieval filters, answer-leak detection) with a strict escalation path:

* **Curriculum intent:** Genuine learning question — Pathwise explains the concept using retrieved curriculum material and ends with a check-for-understanding question.
* **1st answer-seeking attempt:** Friendly redirect + coaching mode — Pathwise names the concept the student needs and asks what they've tried, without writing any code.
* **2nd attempt:** Structured guidance — concept name, plain-English explanation, an analogous example with different values, and a guiding question.
* **3rd attempt:** Complete block — student is redirected to conceptual review with no code or hints.

## Tech Stack
* **Backend:** Python 3.10+ / FastAPI / LangGraph
* **LLM:** Groq (`llama-3.1-8b-instant`)
* **Vector DB:** Databricks Vector Search (`capstone.vector_layer.curriculum_semantic_index`)
* **RAG:** Custom implementation via `databricks-sdk` + `databricks-vectorsearch`
* **Frontend:** React 19 + Vite
* **Infrastructure:** Databricks (workspace, Unity Catalog, Vector Search, Databricks Apps)
* **CI/CD:** GitHub

---

## Prerequisites

Before you start, make sure you have the following installed for local development:

| Tool | Version | Notes |
| --- | --- | --- |
| Python | 3.10+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | comes with Node.js |
| Git | any | `git --version` |

You will also need:

* A **Databricks workspace** with Vector Search enabled and the `capstone.vector_layer.curriculum_semantic_index` index already populated.
* A **Groq API key**.
* A **Databricks personal access token** for local development and Databricks SDK access.

For Databricks Apps deployment, the app runtime requires these environment variables or secrets:

* `GROQ_API_KEY`
* `DATABRICKS_HOST`
* `DATABRICKS_TOKEN`

Do not commit any secret values to git.

---

## Local Development Setup

### Step 1 — Clone the repository

```bash
git clone https://github.com/Team-Three-Brett-Drashti-Mark/team3-hackathon3.git
cd team3-hackathon3
```

### Step 2 — Create your `.env` file

For local development, the backend can read credentials from a `.env` file in the project root.

Create `.env` and set these values:

```text
GROQ_API_KEY=your_groq_api_key
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=your_databricks_pat
```

`app/main.py` now prefers environment variables already present in the runtime and only falls back to `.env` locally if the file exists.

> **Never commit `.env` to git.** It is already listed in `.gitignore`.

### Step 3 — Optional: set up the Databricks VS Code Extension

The Databricks extension can still be useful for browsing workspace assets and resolving `databricks.yml` bundle configuration, but it is not required to run the app locally if your environment variables are already set.

### Step 4 — Create a Python virtual environment and install backend dependencies

Run all of these from the project root:

```bash
python3 -m venv venv

# Mac / Linux:
source venv/bin/activate
# Windows (PowerShell):
venv\Scripts\Activate.ps1
# Windows (Command Prompt):
venv\Scripts\activate.bat

pip install -r requirements.txt
```

`requirements.txt` installs:

```text
langgraph
groq
python-dotenv
fastapi
uvicorn
databricks-sdk
databricks-vectorsearch
```

### Step 5 — Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

This installs React, Vite, and the frontend dependencies listed in `frontend/package.json`.

### Step 6 — Run the app locally

Local development still uses two processes:

* FastAPI backend on port `8000`
* Vite frontend on port `5173`

**Mac / Linux — use `start.sh`:**

```bash
source venv/bin/activate
chmod +x start.sh
./start.sh
```

**Windows — use `start.ps1`:**

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
.\start.ps1
```

The script starts both services, waits for the backend health check, and shuts both down cleanly on `Ctrl+C`.

Open `http://localhost:5173` in your browser to use the local development UI.

---

## Databricks Apps Deployment

This repo can be deployed as a Databricks App from the repo root. The deployment is defined by `app.yaml` at the top level of the repository.

### Hosted app behavior

In the hosted app:

* the React frontend is built into `frontend/dist`
* FastAPI serves the built frontend and the `/chat` API from the same origin
* browser requests use a relative `/chat` path, so no localhost-specific API URL is required in production
* `app/api.py` serves static files and SPA fallback routes

### Required app secrets

Configure these three secret-backed environment variables for the Databricks App:

* `GROQ_API_KEY`
* `DATABRICKS_HOST`
* `DATABRICKS_TOKEN`

### Deploy steps

1. Create a Databricks App asset.
2. Use the app name you want for the deployment, such as `pathwise`.
3. Set the app source path to:
   ` /Workspace/Repos/w.brett.coleman@gmail.com/team3-hackathon3 `
4. Ensure the repo root is used as the deployment root so the app picks up `app.yaml`.
5. Configure the three required secrets or environment variables:
   * `GROQ_API_KEY`
   * `DATABRICKS_HOST`
   * `DATABRICKS_TOKEN`
6. Start the deployment.
7. Watch the Databricks App build logs for the steps defined in `app.yaml`:
   * Python dependency installation from `requirements.txt`
   * frontend dependency installation in `frontend/`
   * frontend build into `frontend/dist`
   * Uvicorn startup for `app.api:app`
8. After deployment completes, verify:
   * the app loads successfully in the browser
   * the UI is served by the FastAPI app
   * `/health` returns an OK response
   * a sample `/chat` flow works end to end

### Notes on the current deployment

The existing app named `pathwise` was deployed from this repo root and uses secret-backed resources for the required runtime credentials. If you redeploy after code changes, deploy from the same repo path so the latest repo-root `app.yaml` is used.

---

## Interaction Logging

Pathwise attempts to log interactions to the configured Delta logging destination. If that write fails, `app/logger.py` falls back to logging the failure details to stdout and appending them to `app.log` in the project root.

A fallback log entry includes fields like:

```text
[timestamp] [DELTA_FAIL: ...]
SESSION: ...
USER INPUT: ...
SYSTEM OUTPUT: ...
INTENT: ...
ATTEMPT: ...
```

`app.log` is excluded from git. Do not commit it.

---

## Repository Structure

```text
team3-hackathon3/
├── app/
│   ├── api.py          # FastAPI app — /chat endpoint, hosted static serving, SPA fallback
│   ├── logger.py       # Interaction logger with Delta write + stdout/app.log fallback
│   └── main.py         # LangGraph graph and runtime env loading logic
├── frontend/
│   ├── src/
│   │   └── App.jsx     # React chat UI — uses relative /chat in hosted mode
│   └── dist/           # Production build output served by FastAPI in Databricks Apps
├── guardrails/
│   └── no_direct_answers.py
├── retrieval/
│   └── retriever.py    # Databricks Vector Search client — returns chunks with metadata
├── start.sh            # One-command local startup (Mac / Linux)
├── start.ps1           # One-command local startup (Windows PowerShell)
├── app.yaml            # Databricks Apps build/run manifest used from the repo root
├── databricks.yml      # Declarative Automation Bundles config for workspace development
├── requirements.txt    # Python backend dependencies
└── .env                # Local secrets for development only — never commit this file
```

---

## User Personas

1. **Marcus (The Struggling Student):** Wants to get unstuck quickly and learn *why* things work.
2. **Priya (The High Performer):** Wants to go deeper into the curriculum and validate her reasoning.
3. **Sandra (The Administrator):** Needs non-technical dashboards to spot struggling students early.
4. **Dev (The Instructor):** Wants to use student question patterns to improve future lessons without babysitting the tool.

---

## Roadmap

### Phase 1: Core Functional MVP (Current)
* Curriculum ingestion & Databricks Vector Search knowledge base
* Student learning assistant (Chat UI + RAG retrieval with multi-turn context)
* Guardrail logic (curriculum / attempt-1 / attempt-2 / hard-block escalation)
* Answer-leak detection with static fallbacks
* Interaction logging
* Databricks Apps hosting support

### Phase 2: Scaled Product Version
* Improved intelligence layer (hybrid search, personalized hint progression)
* Advanced dashboard (at-risk indicators, struggle heatmaps)
* Admin controls (instant curriculum updates)
* Instructor layer (common misconceptions report)
* Better product experience (UI/UX polish, mobile responsiveness)

# Pathwise — Test Suite

## Structure

```text
tests/
├── conftest.py               # Shared fixtures (mock Groq, mock retriever, base states)
├── test_classifier.py        # classify_intent + route_intent unit tests
├── test_guardrails.py        # Guardrail node unit tests (leak detection, fallbacks, hard block)
├── test_retriever.py         # Retriever unit tests (_parse_metadata, retrieve(), chunk filtering)
├── test_api.py               # FastAPI /health + /chat integration tests
├── test_logger.py            # Logger unit tests (format, append, edge cases)
└── test_graph_integration.py # Full end-to-end graph tests (all escalation paths)
```

## Setup

Activate your virtual environment then install the test dependency:

```bash
source venv/bin/activate          # Mac/Linux
# venv\Scripts\activate           # Windows

pip install pytest httpx
```

> `httpx` is required by FastAPI's `TestClient`.

## Running Tests

```bash
# Run the entire suite from the project root
pytest

# Run a specific file
pytest tests/test_classifier.py

# Run a specific test class or function
pytest tests/test_guardrails.py::TestHardBlock
pytest tests/test_classifier.py::TestAnswerSeekingIntent::test_keyword_triggers

# Stop on first failure
pytest -x

# Show print() output while running
pytest -s

# Quiet (dots only)
pytest -q
```

## What Is Mocked

All external I/O is patched so tests run fully offline:

| Dependency | How mocked |
| --- | --- |
| Groq API | `monkeypatch` replaces `Groq(...)` with a `MagicMock` returning canned text |
| Databricks Vector Search | `monkeypatch` replaces `retrieve()` with a list of hardcoded curriculum chunks |
| `app.log` file | `monkeypatch` redirects `open("app.log")` to a `tmp_path` temp file |
| FastAPI server | `TestClient` — no real HTTP server needed |

## Test Coverage by Component

| File | Tests |
| --- | --- |
| `app/main.py` — `classify_intent` | keyword triggers, off-topic, attempt escalation, server-side history re-count |
| `app/main.py` — `route_intent` | all 5 routing branches |
| `app/main.py` — `retrieve_context` | relevance filtering, fallback-to-best-chunk |
| `guardrails/no_direct_answers.py` | leak detection, safe pass-through, hard block static guarantee, LLM fallbacks, history threading |
| `retrieval/retriever.py` | metadata parsing, SDK call parameters, empty/error handling |
| `app/api.py` | 200 responses, request validation, attempt echo, logging side-effect |
| `app/logger.py` | file creation, field presence, append, unicode, edge cases |
| Full graph | all intent paths, multi-turn context, state integrity guarantees |
