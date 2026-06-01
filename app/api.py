import base64
import binascii
import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import admin as admin_module
from app.admin import router as admin_router
from app.logger import log_interaction
from app.main import PathwiseState, build_graph

logger = logging.getLogger(__name__)


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


def _normalize_env_secret(name: str, expected_prefixes: tuple[str, ...]) -> None:
    value = os.getenv(name)
    if not value:
        return

    cleaned = value.strip()
    if any(cleaned.startswith(prefix) for prefix in expected_prefixes):
        os.environ[name] = cleaned
        return

    try:
        decoded = base64.b64decode(cleaned).decode("utf-8").strip()
    except (binascii.Error, UnicodeDecodeError, ValueError):
        os.environ[name] = cleaned
        return

    os.environ[name] = (
        decoded if any(decoded.startswith(prefix) for prefix in expected_prefixes) else cleaned
    )


def _add_check(status: dict, key: str, fn):
    try:
        value = fn()
        status["checks"][key] = {"ok": True, "value": value}
    except Exception as exc:  # noqa: BLE001
        status["checks"][key] = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


# Normalize secrets once at startup so both the student and admin backends use
# the same decoded values. The admin router talks directly to Databricks APIs,
# so if DATABRICKS_HOST was stored base64-encoded the student chat could still
# work after /chat normalized it, while /admin would fail before that ever ran.
_normalize_env_secret("GROQ_API_KEY", ("gsk_",))
_normalize_env_secret("DATABRICKS_HOST", ("https://",))
_normalize_env_secret("DATABRICKS_TOKEN", ("dapi",))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled request failure on %s", request.url.path)
    if request.url.path.startswith("/admin"):
        return JSONResponse(
            status_code=500,
            content={
                "detail": f"{type(exc).__name__}: {exc}",
                "path": request.url.path,
            },
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "path": request.url.path},
    )


app.include_router(admin_router)

# Build the graph once at startup — shared across all requests
graph = build_graph()

_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
_FRONTEND_INDEX = _FRONTEND_DIST / "index.html"

if _FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")


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


@app.get("/admin/debug/status")
def admin_debug_status():
    host = os.getenv("DATABRICKS_HOST", "")
    token = os.getenv("DATABRICKS_TOKEN", "")
    status = {
        "env": {
            "databricks_host_present": bool(host),
            "databricks_host_scheme": host.split(":", 1)[0] if host else None,
            "databricks_token_present": bool(token),
            "databricks_token_prefix": token[:4] if token else None,
            "groq_api_key_present": bool(os.getenv("GROQ_API_KEY")),
        },
        "checks": {},
    }

    _add_check(status, "workspace_client", lambda: "ok" if admin_module._client() else "missing")
    _add_check(
        status,
        "warehouses",
        lambda: [
            {"id": w.id, "name": w.name, "state": str(w.state)}
            for w in list(admin_module._client().warehouses.list())[:5]
        ],
    )
    _add_check(status, "selected_warehouse", admin_module._get_warehouse_id)
    _add_check(status, "sql_select_1", lambda: admin_module._run_sql("SELECT 1 AS ok"))
    _add_check(status, "daily_usage_sample", lambda: admin_module._run_sql("SELECT * FROM v_daily_usage LIMIT 1"))
    _add_check(status, "intent_breakdown_sample", lambda: admin_module._run_sql("SELECT * FROM v_intent_breakdown LIMIT 1"))
    _add_check(status, "hourly_activity_sample", lambda: admin_module._run_sql("SELECT * FROM v_hourly_activity LIMIT 1"))
    _add_check(
        status,
        "curriculum_volume_root",
        lambda: len(list(admin_module._client().files.list_directory_contents(admin_module.VOLUME_ROOT))),
    )
    return status


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
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
