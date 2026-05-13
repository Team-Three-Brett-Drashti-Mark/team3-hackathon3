# Team 3 Hackathon: Private Learning Assistant

## 📌 Problem Statement
Cohort-based learning programs lack a scalable system that can help students learn through guided support without giving direct answers, while also giving instructors and administrators visibility into learning progress and struggles.

## 💡 The Solution
We built a private learning assistant that sits directly on top of a program’s curriculum. 

Instead of just answering questions like a typical chatbot, our system acts as a guide. When students ask questions in natural language, it points them to the right material, asks follow-up questions, and helps them think through the problem without giving the final answer. Meanwhile, instructors and administrators gain deep visibility into what’s actually happening: which topics are asked about most, where students get stuck, and which parts of the curriculum are heavily referenced.

## 🏗️ Architecture & Pipeline
We designed a robust Bronze, Silver, Gold data pipeline:
- **Bronze Layer:** Raw curriculum ingestion (PDFs, Markdown, text, quizzes, rubrics).
- **Silver Layer:** Processing, cleaning, deduplication, and chunking. Metadata (e.g., week, topic, assignment type) is added to make the data structured and searchable.
- **Gold Layer:** Embeddings are stored in a vector database connected to a retriever.

*Workflow:* Student queries are intercepted to retrieve the most relevant curriculum first. This is passed through our **Guardrail Layer** which enforces the "no direct answers" rule, before the LLM generates a guided response. System logs feed directly into admin insights.

## 🛡️ Guardrail Philosophy
A core feature of the product is ensuring students *learn* rather than copy-paste solutions. We enforce this through multiple layers (intent detection, policy engine, retrieval filters, etc.) with a strict escalation path:

- **1st Attempt:** Friendly redirect + coaching mode (e.g., *"I won’t give the direct answer, but I can help you solve it. What have you tried so far?"*)
- **2nd Attempt:** Structured guidance + concept reminders.
- **3rd Attempt:** Complete block of answer-seeking behavior with a redirect to conceptual review. 

## 🛠️ Tech Stack
- **Backend:** Python / FastAPI
- **LLM:** Local model or API
- **Vector DB:** FAISS / Pinecone / PGVector / Chroma
- **RAG:** Full custom implementation
- **Frontend:** React (or HTML/CSS/JS)
- **Data / Infrastructure:** Databricks
- **CI/CD:** GitHub

## 🎯 User Personas
Our solution targets four core users:
1. **Marcus (The Struggling Student):** Wants to get unstuck quickly and learn *why* things work.
2. **Priya (The High Performer):** Wants to go deeper into the curriculum and validate her reasoning.
3. **Sandra (The Administrator):** Needs non-technical dashboards to spot struggling students early.
4. **Dev (The Instructor):** Wants to use student question patterns to improve future lessons without babysitting the tool.

## 🚀 Scope & Roadmap

### Phase 1: Core Functional MVP (Current)
- Curriculum Ingestion (PDF / Markdown / Text) & Knowledge Base Setup
- Student Learning Assistant (Chat UI + RAG Retrieval)
- Guardrail Logic (Attempt 1, 2, 3 system)
- Basic Logging & Role Access (Student vs. Admin)

### Phase 2: Scaled Product Version
- Improved Intelligence Layer (Hybrid search, personalized hint progression)
- Advanced Dashboard (At-risk indicators, struggle heatmaps)
- Admin Controls (Instant curriculum updates)
- Instructor Layer (Common misconceptions report)
- Better Product Experience (UI/UX polish, mobile responsiveness)

## 📁 Repository Structure
- `/ux_workflows`: User experience flows for our personas (Marcus & Sandra).
- `/presentation`: Pitch decks and hackathon presentations.
- Documentation for personas, tech stack, problem statements, and MVP scopes are available in the root folder.


Installation

Clone the repository and install dependencies:

npm install
Running the App

Start the development server:

npm run dev

Open the local development URL shown in the terminal, usually:

http://localhost:5173