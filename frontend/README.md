# Pathwise — Frontend

React 19 + Vite frontend for the Pathwise student learning assistant.

## Local development

```bash
npm install
npm run dev        # starts Vite on http://localhost:5173
```

The dev server proxies `/chat` to `http://localhost:8000` via `VITE_API_BASE_URL`.
Make sure the FastAPI backend is running before testing the AI tutor panel.

## Production build

```bash
npm run build      # outputs to frontend/dist/
```

FastAPI serves `dist/` as static files in the hosted Databricks App — no separate
Node server is needed in production.

## Project structure

```
src/
├── App.jsx                        # Root router — renders <StudentApp /> now
│                                  # Wire in <AdminApp /> here when the admin view is ready
├── App.css                        # Global styles (e.g. .thinking pulse animation)
├── student/                       # All student-facing UI
│   ├── index.jsx                  # Layout, drag handles, and question-transition handlers
│   ├── data/
│   │   └── lessonContent.js       # Lesson text and question definitions — edit content here
│   ├── services/
│   │   └── chatApi.js             # Single fetch call to /chat — no React, easy to unit-test
│   ├── hooks/
│   │   ├── useQuiz.js             # Answer validation, progress, and navigation state
│   │   └── useChat.js             # Chat history, session ID, loading state, auto-scroll
│   ├── styles/
│   │   └── theme.js               # Color tokens and shared labelStyle — change colors here
│   └── components/
│       ├── Navbar.jsx             # Top bar: logo, unit subtitle, progress badge
│       ├── ChatPanel.jsx          # AI tutor: message list, typing indicator, input bar
│       ├── ProgressStrip.jsx      # Unit pill navigation and completion counter
│       ├── LessonPanel.jsx        # Lesson reference card (height controlled by drag state)
│       ├── QuestionPanel.jsx      # Question prompt, code editor, feedback bar, buttons
│       └── UnitComplete.jsx       # Completion screen with Start Over
└── admin/
    └── index.jsx                  # Placeholder — not yet wired into App.jsx
```

## Adding a new lesson unit

1. Open `src/student/data/lessonContent.js`.
2. Update `PAGE_SUBTITLE` if the unit number changes.
3. Add a new entry to the `QUESTIONS` array with `unit`, `text`, `accepted`, and `hint` fields.
4. Update `LESSON_INTRO` / `LESSON_BODY` if the reference content changes.

No other files need to change — the question count and progress strip update automatically.

## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend base URL | `""` (same origin — works for hosted app) |

For local development, create `frontend/.env.local`:

```
VITE_API_BASE_URL=http://localhost:8000
```
