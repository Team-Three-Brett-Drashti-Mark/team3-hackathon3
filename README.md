# Pathwise — Private Learning Assistant

## Problem Statement
Cohort-based learning programs lack a scalable system that can help students learn through guided support without giving direct answers, while also giving instructors and administrators visibility into learning progress and struggles.

## The Solution
We built a private learning assistant that sits directly on top of a program's curriculum.

Instead of just answering questions like a typical chatbot, our system acts as a guide. When students ask questions in natural language, it points them to the right material, asks follow-up questions, and helps them think through the problem without giving the final answer. Meanwhile, instructors and administrators gain deep visibility into what's actually happening: which topics are asked about most, where students get stuck, and which parts of the curriculum are heavily referenced.

## Runtime Modes
Pathwise runs in two ways:

* Local development mode for iteration on a laptop or workstation.
* Hosted deployment on Render as a single public web service.

In local development, the project runs as two processes:

* FastAPI backend on `http://localhost:8000`
* Vite frontend on `http://localhost:5173`

The Vite dev server proxies all `/admin`, `/chat`, and `/quiz` requests to the backend automatically, so no separate API base URL configuration is needed during development.

In the hosted Render deployment, the frontend and backend are a single service on one origin:

* `app/api.py` serves the built React frontend from `frontend/dist`
* the frontend calls `/chat` using a relative URL, so it works on the same origin without a hardcoded backend host
* `app/api.py` also provides static asset serving and SPA fallback routing
* `app/main.py` prefers runtime-injected environment variables and uses `.env` only as a local fallback
* `app/logger.py` writes fallback logging information to stdout as well as `app.log`

## Current Deployment
Pathwise is deployed on **Render** as a web service named `pathwise`, built directly from this repo's `render.yaml`. Render hosts the web tier; the data and retrieval backend still live in Databricks (Unity Catalog, Vector Search, and Delta logging), which the service reaches using the `DATABRICKS_HOST` / `DATABRICKS_TOKEN` credentials.

* Student app: https://pathwise-8vr8.onrender.com
* Admin dashboard: https://pathwise-8vr8.onrender.com/#/admin

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
* **Hosting:** Render (single Python web service built from `render.yaml`)
* **Data & Retrieval:** Databricks (Unity Catalog, Vector Search, Delta logging)
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

For the hosted Render deployment, the service requires these environment variables (configured as secrets in the Render dashboard):

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
python-multipart
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

Open `http://localhost:5173` in your browser for the student view, or `http://localhost:5173/#/admin` for the admin dashboard.

---

## Render Deployment

The app is deployed to Render as a single web service, defined by `render.yaml` at the repo root. Render builds the frontend and runs the FastAPI backend that serves it, so the frontend and API share one origin.

### Hosted app behavior

In the hosted service:

* the React frontend is built into `frontend/dist` during the Render build step
* FastAPI serves the built frontend and the `/chat` + `/admin/*` APIs from the same origin
* browser requests use relative paths, so no environment-specific API URL is required in production
* `app/api.py` serves static files and SPA fallback routes

### How `render.yaml` is configured

* **Runtime:** Python web service
* **Build command** — installs Python deps, then builds the frontend:
  ```bash
  pip install -r requirements.txt
  cd frontend && npm ci && npm run build && cd ..
  ```
* **Start command:** `uvicorn app.api:app --host 0.0.0.0 --port $PORT` (Render injects `$PORT`)
* **Secrets:** `GROQ_API_KEY`, `DATABRICKS_HOST`, and `DATABRICKS_TOKEN` are declared with `sync: false`, so their values are set in the Render dashboard and never committed to git

### Deploy steps

1. In Render, create a new **Blueprint** from this repository (Render reads `render.yaml`), or a Web Service pointed at the repo.
2. Set the three secret values in the Render dashboard:
   * `GROQ_API_KEY`
   * `DATABRICKS_HOST`
   * `DATABRICKS_TOKEN`
3. Deploy. Render runs the build command, then the start command.
4. After deployment, verify:
   * the app loads in the browser at the Render URL
   * `/health` returns an OK response
   * a sample `/chat` flow works end to end
   * the admin dashboard at `/#/admin` loads metrics (the Databricks SQL warehouse must be running)

### Notes on the current deployment

Render auto-deploys on pushes to the connected branch, so committing changes redeploys the app. The Databricks SQL warehouse that backs the admin metrics bills while it runs — keep its auto-stop low (~10 min) so it idles down between sessions. The first admin request after the warehouse idles waits ~15–30s while it wakes; that delay is Databricks-side, not Render.

---

## Interaction Logging

Pathwise logs every interaction to the configured Delta logging destination. If a Delta write fails, `app/logger.py` automatically falls back to writing the failure details to stdout and appending them to `app.log` in the project root — so no interaction is ever silently dropped, and the audit trail survives transient backend outages.

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
│   ├── api.py               # FastAPI app — /chat, /admin/* endpoints, hosted static serving
│   ├── admin.py             # Admin API router — metrics, curriculum volume, audit log
│   ├── logger.py            # Interaction logger with Delta write + stdout/app.log fallback
│   └── main.py              # LangGraph graph and runtime env loading logic
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Root hash router — #/admin → AdminApp, default → StudentApp
│   │   ├── student/         # All student-facing UI (see Frontend Architecture below)
│   │   └── admin/           # Admin dashboard (see Frontend Architecture below)
│   ├── vite.config.js       # Dev server proxy — /admin, /chat, /quiz → localhost:8000
│   └── dist/                # Production build output served by FastAPI on Render
├── guardrails/
│   └── no_direct_answers.py
├── retrieval/
│   └── retriever.py         # Databricks Vector Search client — returns chunks with metadata
├── start.sh                 # One-command local startup (Mac / Linux)
├── start.ps1                # One-command local startup (Windows PowerShell)
├── render.yaml              # Render build/start manifest used for deployment
├── databricks.yml           # Declarative Automation Bundles config for the data/ingestion workspace
├── requirements.txt         # Python backend dependencies
└── .env                     # Local secrets for development only — never commit this file
```

---

## Frontend Architecture

`App.jsx` at the root is a thin hash-based router: visiting `/#/admin` renders the admin dashboard, everything else renders the student view.

```text
frontend/src/
├── App.jsx                        # Root router — hash #/admin → AdminApp, default → StudentApp
├── App.css                        # Global styles (e.g. .thinking animation)
├── student/
│   ├── index.jsx                  # Student view root — layout, drag handles, transition handlers
│   ├── data/
│   │   └── lessonContent.js       # Lesson text, unit subtitle, and question definitions
│   ├── services/
│   │   └── chatApi.js             # Fetch call to /chat — plain async function, no React
│   ├── hooks/
│   │   ├── useQuiz.js             # Answer validation, progress, and question-navigation state
│   │   └── useChat.js             # Chat history, session ID, loading state, and scroll effect
│   ├── styles/
│   │   └── theme.js               # Shared color tokens and labelStyle used by both views
│   └── components/
│       ├── Navbar.jsx             # Top bar: branding, unit subtitle, progress badge
│       ├── ChatPanel.jsx          # AI tutor panel: message list, typing indicator, input bar
│       ├── ProgressStrip.jsx      # Unit pill buttons and completion counter
│       ├── LessonPanel.jsx        # Lesson reference card — height driven by parent drag state
│       ├── QuestionPanel.jsx      # Question prompt, compact code editor, feedback, buttons
│       └── UnitComplete.jsx       # Completion screen with Start Over button
└── admin/
    ├── index.jsx                  # Admin root — sidebar nav + content area
    ├── components/
    │   └── Sidebar.jsx            # Left nav: Overview, Curriculum, Audit Log, Ask
    ├── hooks/
    │   ├── useOverviewMetrics.js  # Fetches /admin/metrics/overview
    │   ├── useCurriculum.js       # Curriculum volume state machine (weeks → folders → files)
    │   └── useAuditLog.js         # Paginated audit log fetch with intent filter
    ├── services/
    │   └── adminApi.js            # All /admin/* fetch calls — plain async functions, no React
    └── pages/
        ├── Overview/
        │   ├── index.jsx              # Stat cards + daily / hourly / intent charts
        │   ├── StatCard.jsx           # Single metric tile with optional highlight
        │   ├── DailyUsageChart.jsx    # Inline SVG bar chart (questions per day, M/D labels)
        │   ├── HourlyActivityChart.jsx# Inline SVG bar chart (activity by hour 0–23)
        │   └── IntentBreakdownChart.jsx # Horizontal CSS bars (curriculum / answer_seeking / off_topic)
        ├── Curriculum/
        │   ├── index.jsx              # Week list → folder list → file list drill-down
        │   └── FileDropZone.jsx       # HTML5 drag-and-drop + click-to-browse uploader
        ├── AuditLog/
        │   ├── index.jsx              # Paginated table with intent filter
        │   └── LogRow.jsx             # Expandable row showing full student + Pathwise message pair
        └── Ask/
            └── index.jsx              # Natural-language admin query — UI scaffolded, query backend in Phase 2
```

### Admin dashboard

Navigate to `http://localhost:5173/#/admin` to open the admin dashboard. It requires the backend to be running (the Vite proxy forwards all `/admin/*` requests to port 8000).

| Page | What it shows |
|---|---|
| **Overview** | Live operational dashboard: stat tiles, a daily-usage bar chart, an hourly-activity chart across the full 0–23 range, an intent-breakdown chart (curriculum / answer-seeking / off-topic), and a count of sessions that hit the hard block. All charts render from real logging data via dedicated SVG/CSS components — no external charting dependency |
| **Curriculum** | Full content-management surface over the Bronze-layer volume (`/Volumes/capstone/bronze_layer/curriculum_raw`): drill through week → folder → files, upload via HTML5 drag-and-drop or click-to-browse, and create new week folders — all backed by live volume reads and writes |
| **Audit Log** | Paginated, intent-filterable table of every interaction from `capstone.logging.interaction_logs` — click any row to expand the full student message and Pathwise reply for that turn |
| **Ask** | Natural-language query interface over the interaction and curriculum data. The page, navigation, and UX copy are in place; the query backend lands in Phase 2 |

Metrics are sourced from three pre-built Databricks views in `capstone.logging`:

* `v_daily_usage` — interactions per day
* `v_hourly_activity` — interactions by hour of day
* `v_intent_breakdown` — counts per intent label

### Resizable student layout

The student view has two drag handles:

* **Vertical divider** between the AI tutor (left) and content columns (right) — drag left/right to widen or narrow the chat panel (clamped 20–65 % of viewport width).
* **Horizontal divider** between the lesson reference card and the question/answer area — drag up/down to give the lesson more or less space (clamped 120–420 px).

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
* Interaction logging to `capstone.logging.interaction_logs`
* Render hosting (public web service)
* Admin dashboard — usage metrics, curriculum volume management, audit log

### Phase 2: Scaled Product Version
* Improved intelligence layer (hybrid search, personalized hint progression)
* Advanced dashboard (at-risk indicators, struggle heatmaps, per-student drill-down)
* Instructor layer (common misconceptions report, question pattern analysis)
* Admin Ask interface (natural-language queries over the logging data)
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
