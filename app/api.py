import base64
import binascii
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.admin import router as admin_router
from app.logger import log_interaction
from app.main import PathwiseState, build_graph


# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(title="Pathwise API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router)

# Build the graph once at startup — shared across all requests
graph = build_graph()

_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
_FRONTEND_INDEX = _FRONTEND_DIST / "index.html"

if _FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")


def _normalize_env_secret(name: str, expected_prefix: str) -> None:
    value = os.getenv(name)
    if not value:
        return

    cleaned = value.strip()
    if cleaned.startswith(expected_prefix):
        os.environ[name] = cleaned
        return

    try:
        decoded = base64.b64decode(cleaned).decode("utf-8").strip()
    except (binascii.Error, UnicodeDecodeError, ValueError):
        os.environ[name] = cleaned
        return

    os.environ[name] = decoded if decoded.startswith(expected_prefix) else cleaned


class ChatRequest(BaseModel):
    user_input: str
    lesson_context: str = ""
    attempt: int = 1
    session_id: str = ""
    conversation_history: list[dict] = []


class ChatResponse(BaseModel):
    response_text: str
    intent: str
    attempt: int


@app.get("/health")
def health():
    return {
        "status": "ok",
        "frontend_built": _FRONTEND_INDEX.exists(),
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        _normalize_env_secret("GROQ_API_KEY", "gsk_")
        _normalize_env_secret("DATABRICKS_HOST", "https://")

        result = graph.invoke(
            PathwiseState(
                user_input=req.user_input,
                lesson_context=req.lesson_context,
                conversation_history=req.conversation_history,
                retrieved_chunks=[],
                intent="",
                attempt=req.attempt,
                response_text="",
            )
        )

        log_interaction(
            session_id=req.session_id,
            user_input=req.user_input,
            system_output=result["response_text"],
            intent=result["intent"],
            attempt=req.attempt,
        )

        return ChatResponse(
            response_text=result["response_text"],
            intent=result["intent"],
            attempt=req.attempt,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Chat backend error: {type(exc).__name__}: {exc}",
        ) from exc


@app.get("/{full_path:path}")
def serve_frontend(full_path: str):
    if _FRONTEND_INDEX.exists():
        requested = _FRONTEND_DIST / full_path
        if full_path and requested.exists() and requested.is_file():
            return FileResponse(requested)
        return FileResponse(_FRONTEND_INDEX)
    return {
        "message": "Frontend build not found. Run `npm run build` in frontend/ before serving the app.",
        "requested_path": full_path,
    }
