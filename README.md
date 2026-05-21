# Pathwise — Private Learning Assistant

## Problem Statement
Cohort-based learning programs lack a scalable system that can help students learn through guided support without giving direct answers, while also giving instructors and administrators visibility into learning progress and struggles.

## The Solution
We built a private learning assistant that sits directly on top of a program's curriculum.

Instead of just answering questions like a typical chatbot, our system acts as a guide. When students ask questions in natural language, it points them to the right material, asks follow-up questions, and helps them think through the problem without giving the final answer. Meanwhile, instructors and administrators gain deep visibility into what's actually happening: which topics are asked about most, where students get stuck, and which parts of the curriculum are heavily referenced.

## Architecture & Pipeline
We designed a robust Bronze, Silver, Gold data pipeline:
- **Bronze Layer:** Raw curriculum ingestion (PDFs, Markdown, text, quizzes, rubrics).
- **Silver Layer:** Processing, cleaning, deduplication, and chunking. Metadata (e.g., week, topic, assignment type) is added to make the data structured and searchable.
- **Gold Layer:** Embeddings are stored in a Databricks Vector Search index connected to a retriever.

*Workflow:* Student queries are intercepted to retrieve the most relevant curriculum first. This is passed through our **Guardrail Layer** which enforces the "no direct answers" rule, before the LLM generates a guided response. System logs feed directly into admin insights.

## Guardrail Philosophy
A core feature of the product is ensuring students *learn* rather than copy-paste solutions. We enforce this through multiple layers (intent detection, policy engine, retrieval filters, answer-leak detection) with a strict escalation path:

- **Curriculum intent:** Genuine learning question — Pathwise explains the concept using retrieved curriculum material and ends with a check-for-understanding question.
- **1st answer-seeking attempt:** Friendly redirect + coaching mode — Pathwise names the concept the student needs and asks what they've tried, without writing any code.
- **2nd attempt:** Structured guidance — concept name, plain-English explanation, an analogous example with different values, and a guiding question.
- **3rd attempt:** Complete block — student is redirected to conceptual review with no code or hints.

## Tech Stack
- **Backend:** Python 3.10+ / FastAPI / LangGraph
- **LLM:** Groq (`llama-3.1-8b-instant`)
- **Vector DB:** Databricks Vector Search (`capstone.vector_layer.curriculum_semantic_index`)
- **RAG:** Custom implementation via `databricks-sdk` + `databricks-vectorsearch`
- **Frontend:** React 19 + Vite
- **Infrastructure:** Databricks (workspace, Unity Catalog, Vector Search)
- **CI/CD:** GitHub

---

## Prerequisites

Before you start, make sure you have the following installed:

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.10+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | comes with Node.js |
| Git | any | `git --version` |

You will also need:
- A **Databricks workspace** with Vector Search enabled and the `capstone.vector_layer.curriculum_semantic_index` index already populated.
- A **Groq API key** — get one free at [console.groq.com](https://console.groq.com).
- A **Databricks personal access token** (Settings → Developer → Access tokens in your workspace).

---

## Step-by-Step Setup

### Step 1 — Clone the repository

```bash
git clone https://github.com/Team-Three-Brett-Drashti-Mark/team3-hackathon3.git
cd team3-hackathon3
```

---

### Step 2 — Create your `.env` file

The backend reads credentials from a `.env` file in the project root. Create it now:

```bash
cp .env .env.backup   # optional — back up any existing file
```

Open `.env` in your editor and set these three values:

```
GROQ_API_KEY=gsk_your_groq_key_here
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapiyour_databricks_token_here
```

- `GROQ_API_KEY` — your Groq API key (starts with `gsk_`).
- `DATABRICKS_HOST` — the full URL of your Databricks workspace (no trailing slash).
- `DATABRICKS_TOKEN` — your Databricks personal access token (starts with `dapi`).

> **Never commit `.env` to git.** It is already listed in `.gitignore`.

---

### Step 3 — Set up the Databricks VS Code Extension

The Databricks extension connects VS Code directly to your workspace for browsing notebooks, running jobs, and (in this project) resolving the `databricks.yml` bundle configuration.

**3a. Install the extension**

1. Open VS Code.
2. Go to the Extensions panel (`Cmd+Shift+X` on Mac / `Ctrl+Shift+X` on Windows).
3. Search for **Databricks** and install the extension published by **Databricks**.

**3b. Open the project**

Open the `team3-hackathon3` folder in VS Code. The extension automatically detects `databricks.yml` in the project root and reads the workspace host from it:

```yaml
# databricks.yml (already in the repo — no edits needed)
bundle:
  name: team3-hackathon3
targets:
  dev:
    mode: development
    default: true
    workspace:
      host: https://dbc-05589632-7e63.cloud.databricks.com
```

**3c. Sign in to your workspace**

1. Click the Databricks icon in the VS Code Activity Bar (left sidebar).
2. Click **Configure Databricks** if prompted, or use the workspace dropdown at the top of the Databricks panel.
3. Select **Add new workspace** → paste your `DATABRICKS_HOST` URL.
4. Choose **Personal Access Token** as the auth method → paste your `DATABRICKS_TOKEN`.
5. The extension will show a green checkmark and your workspace name when connected.

**3d. Verify the connection**

In the Databricks panel you should be able to expand **Catalog** and navigate to `capstone → vector_layer → curriculum_semantic_index` to confirm the Vector Search index is reachable.

> **Note:** The extension is used here for workspace visibility and bundle management. The backend connects to Databricks at runtime using the SDK credential chain — it reads `DATABRICKS_HOST` and `DATABRICKS_TOKEN` from `.env`, so the app will work even without the extension as long as those env vars are set.

---

### Step 4 — Create a Python virtual environment and install dependencies

Run all of these from the **project root**:

```bash
# Create the virtual environment
python3 -m venv venv

# Activate it
# Mac / Linux:
source venv/bin/activate
# Windows (PowerShell):
venv\Scripts\Activate.ps1
# Windows (Command Prompt):
venv\Scripts\activate.bat

# Install backend dependencies
pip install -r requirements.txt
```

`requirements.txt` installs:

```
langgraph
groq
python-dotenv
fastapi
uvicorn
databricks-sdk
databricks-vectorsearch
```

---

### Step 5 — Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

This installs React 19, Vite, and the other frontend packages listed in `frontend/package.json`.

---

### Step 6 — Run the app

Both startup scripts launch the FastAPI backend on port **8000** and the Vite frontend on port **5173**, wait for the backend to be ready, and shut both down cleanly on `Ctrl+C`.

**Mac / Linux — use `start.sh`:**

```bash
# Make sure the venv is active first (Step 4 above)
source venv/bin/activate

chmod +x start.sh   # only needed once
./start.sh
```

**Windows — use `start.ps1`:**

```powershell
# If you get an execution-policy error, run this once as Administrator:
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# Then from the project root:
.\start.ps1
```

The script will print the following when everything is up:

```
============================================
  Pathwise is running!
  Frontend: http://localhost:5173
  Backend:  http://localhost:8000
  Press Ctrl+C to stop both servers.
============================================
```

Open **http://localhost:5173** in your browser to use the app.

---

## Interaction Logging

Every chat turn is logged to `app.log` in the project root (created automatically on first use). Each entry records:

```
[2026-05-20 14:32:01]
USER INPUT: how do I slice a string
SYSTEM OUTPUT: Great question! Look at the string slicing section...
INTENT: curriculum
ATTEMPT: 1
--------------------------------------------------
```

`app.log` is excluded from git. Do not commit it.

---

## Repository Structure

```
team3-hackathon3/
├── app/
│   ├── api.py          # FastAPI app — /chat endpoint, request/response models
│   ├── logger.py       # Interaction logger → app.log
│   └── main.py         # LangGraph graph: state, nodes, routing logic
├── frontend/
│   └── src/
│       └── App.jsx     # React chat UI — sends conversation_history each turn
├── guardrails/
│   └── no_direct_answers.py  # Groq LLM nodes: curriculum_response, guide_response,
│                              # structured_hint, hard_block + answer-leak detection
├── retrieval/
│   └── retriever.py    # Databricks Vector Search client — returns chunks with metadata
├── start.sh            # One-command startup (Mac / Linux)
├── start.ps1           # One-command startup (Windows PowerShell)
├── databricks.yml      # Databricks Asset Bundle config — points to the workspace
├── requirements.txt    # Python backend dependencies
└── .env                # Local secrets — never commit this file
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
- Curriculum ingestion & Databricks Vector Search knowledge base
- Student learning assistant (Chat UI + RAG retrieval with multi-turn context)
- Guardrail logic (curriculum / attempt-1 / attempt-2 / hard-block escalation)
- Answer-leak detection with static fallbacks
- Interaction logging

### Phase 2: Scaled Product Version
- Improved intelligence layer (hybrid search, personalized hint progression)
- Advanced dashboard (at-risk indicators, struggle heatmaps)
- Admin controls (instant curriculum updates)
- Instructor layer (common misconceptions report)
- Better product experience (UI/UX polish, mobile responsiveness)
