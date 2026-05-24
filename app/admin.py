import io
import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementResponse, StatementState

_TERMINAL = {StatementState.SUCCEEDED, StatementState.FAILED,
             StatementState.CANCELED, StatementState.CLOSED}

# ── Constants ─────────────────────────────────────────────────────────────────

VOLUME_ROOT = "/Volumes/capstone/bronze_layer/curriculum_raw"
# Standard subfolders created with every new week.
WEEK_SUBFOLDERS = ["markdown", "pdfs", "quizzes"]

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _client() -> WorkspaceClient:
    return WorkspaceClient(
        host=os.environ["DATABRICKS_HOST"],
        token=os.environ["DATABRICKS_TOKEN"],
    )


def _get_warehouse_id(client: WorkspaceClient) -> str:
    """Prefer a running warehouse so we don't wait for a cold start on every request."""
    warehouses = list(client.warehouses.list())
    if not warehouses:
        raise HTTPException(status_code=500, detail="No SQL warehouses available")
    # Prefer one that's already running; fall back to the first available.
    running = [w for w in warehouses if str(w.state).upper() == "RUNNING"]
    chosen = (running or warehouses)[0]
    if chosen.id is None:
        raise HTTPException(status_code=500, detail="No SQL warehouses available")
    return chosen.id


def _poll(client: WorkspaceClient, statement_id: str) -> StatementResponse:
    """Poll until the statement reaches a terminal state (handles warehouse cold starts)."""
    for _ in range(24):          # up to ~4 minutes of polling
        resp = client.statement_execution.get_statement(statement_id)
        if (resp.status.state if resp.status else None) in _TERMINAL:
            return resp
        time.sleep(10)
    raise HTTPException(status_code=504, detail="SQL statement timed out")


def _execute(client: WorkspaceClient, sql: str) -> StatementResponse:
    """Submit a statement and block until it completes, polling if the warehouse is cold."""
    resp = client.statement_execution.execute_statement(
        warehouse_id=_get_warehouse_id(client),
        statement=sql,
        catalog="capstone",
        schema="logging",
        wait_timeout="50s",   # maximum synchronous wait the API allows
    )
    state = resp.status.state if resp.status else None
    if state not in _TERMINAL:
        if not resp.statement_id:
            raise HTTPException(status_code=500, detail="No statement ID returned")
        resp = _poll(client, resp.statement_id)
        state = resp.status.state if resp.status else None

    if state != StatementState.SUCCEEDED:
        err = resp.status.error.message if resp.status and resp.status.error else str(state)
        raise HTTPException(status_code=500, detail=err)
    return resp


def _run_sql(sql: str) -> list[list]:
    """Execute SQL and return rows as list-of-lists."""
    client = _client()
    resp = _execute(client, sql)
    return (resp.result.data_array or []) if resp.result else []


def _query_view(view_name: str) -> list[dict]:
    """
    Query a pre-built view and return rows as dicts keyed by column name.
    Column names come from the statement execution manifest so we never
    hard-code them — the normalizers below handle the column-name mapping.
    """
    client = _client()
    resp = _execute(client, f"SELECT * FROM {view_name}")
    schema = resp.manifest.schema if resp.manifest else None
    cols = [c.name for c in schema.columns] if schema and schema.columns else []
    rows = (resp.result.data_array or []) if resp.result else []
    return [dict(zip(cols, row)) for row in rows] if cols else []


# ── View column normalizers ───────────────────────────────────────────────────
# Each view may use slightly different column names; these helpers try common
# variants so the frontend always receives a consistent shape.

def _get(row: dict, *keys):
    """Return the first non-None value found among the given keys."""
    for k in keys:
        v = row.get(k)
        if v is not None:
            return v
    return None


def _normalize_daily(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        date = _get(r, "date", "usage_date", "log_date", "dt", "activity_date")
        count = _get(r, "total_interactions", "question_count", "total_questions", "count", "n", "total")
        if date is not None:
            out.append({"date": str(date), "count": int(count or 0)})
    return sorted(out, key=lambda x: x["date"])


def _normalize_intent(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        intent = _get(r, "intent", "intent_type", "intent_label")
        count = _get(r, "question_count", "total_questions", "count", "n", "total")
        if intent is not None:
            out.append({"intent": str(intent), "count": int(count or 0)})
    return out


def _normalize_hourly(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        hour = _get(r, "hour_of_day", "hour", "activity_hour", "h", "hour_bucket")
        count = _get(r, "total_interactions", "question_count", "total_questions", "count", "n", "total")
        if hour is not None:
            out.append({"hour": int(hour), "count": int(count or 0)})
    return sorted(out, key=lambda x: x["hour"])


# ── Overview Metrics ──────────────────────────────────────────────────────────

@router.get("/metrics/overview")
def get_overview():
    """
    Returns daily question counts (v_daily_usage), hourly activity
    (v_hourly_activity), intent breakdown (v_intent_breakdown), and a count
    of sessions that hit the hard block — the only metric not yet in a view.
    """
    daily = _normalize_daily(_query_view("v_daily_usage"))
    intent_breakdown = _normalize_intent(_query_view("v_intent_breakdown"))
    hourly_activity = _normalize_hourly(_query_view("v_hourly_activity"))

    # Sessions that reached attempt >= 3 triggered the hard block.
    # No view exists for this yet, so we query interaction_logs directly.
    behind_rows = _run_sql("""
        SELECT COUNT(DISTINCT session_id) AS n
        FROM interaction_logs
        WHERE attempt >= 3
          AND timestamp >= DATE_SUB(CURRENT_DATE(), 7)
    """)

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total_today = next((d["count"] for d in daily if d["date"] == today_str), 0)
    total_week = sum(d["count"] for d in daily)

    return {
        "daily": daily,
        "hourly_activity": hourly_activity,
        "total_today": total_today,
        "total_week": total_week,
        "behind_count": int(behind_rows[0][0]) if behind_rows and behind_rows[0][0] else 0,
        "intent_breakdown": intent_breakdown,
    }


# ── Curriculum / Volume ───────────────────────────────────────────────────────

@router.get("/curriculum/weeks")
def list_weeks():
    """Lists top-level week folders in the Bronze curriculum volume."""
    client = _client()
    try:
        entries = list(client.files.list_directory_contents(VOLUME_ROOT))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    weeks = [
        {
            "name": (e.path or "").rstrip("/").split("/")[-1],
            "path": e.path,
        }
        for e in entries
        if e.is_directory
    ]
    return {"weeks": weeks}


class CreateWeekRequest(BaseModel):
    week_name: str


@router.post("/curriculum/weeks")
def create_week(body: CreateWeekRequest):
    """Creates a new week folder with the standard markdown/, pdfs/, quizzes/ subfolders."""
    name = body.week_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="week_name is required")

    client = _client()
    week_root = f"{VOLUME_ROOT}/{name}"

    try:
        for subfolder in WEEK_SUBFOLDERS:
            client.files.create_directory(f"{week_root}/{subfolder}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"created": name, "subfolders": WEEK_SUBFOLDERS}


@router.get("/curriculum/weeks/{week}/{folder}")
def list_folder_files(week: str, folder: str):
    """Lists files inside a specific folder of a week."""
    if folder not in WEEK_SUBFOLDERS:
        raise HTTPException(status_code=400, detail=f"folder must be one of {WEEK_SUBFOLDERS}")

    path = f"{VOLUME_ROOT}/{week}/{folder}"
    client = _client()

    try:
        entries = list(client.files.list_directory_contents(path))
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    files = [
        {
            "name": (e.path or "").rstrip("/").split("/")[-1],
            "path": e.path,
            "size_bytes": e.file_size,
            # last_modified is epoch milliseconds; convert to ISO string
            "last_modified": (
                datetime.fromtimestamp(e.last_modified / 1000, tz=timezone.utc).isoformat()
                if e.last_modified else None
            ),
        }
        for e in entries
        if not e.is_directory
    ]
    return {"files": files, "week": week, "folder": folder}


@router.post("/curriculum/weeks/{week}/{folder}/upload")
async def upload_file(week: str, folder: str, file: UploadFile = File(...)):
    """Uploads a file into the specified week/folder in the Volume."""
    if folder not in WEEK_SUBFOLDERS:
        raise HTTPException(status_code=400, detail=f"folder must be one of {WEEK_SUBFOLDERS}")

    content = await file.read()
    path = f"{VOLUME_ROOT}/{week}/{folder}/{file.filename}"

    client = _client()
    try:
        client.files.upload(file_path=path, contents=io.BytesIO(content), overwrite=True)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"uploaded": file.filename, "path": path}


class DeleteFileRequest(BaseModel):
    path: str


@router.delete("/curriculum/file")
def delete_file(body: DeleteFileRequest):
    """Deletes a single file from the Volume."""
    # Guard against deleting outside the curriculum volume.
    if not body.path.startswith(VOLUME_ROOT):
        raise HTTPException(status_code=400, detail="Path is outside the curriculum volume")

    client = _client()
    try:
        client.files.delete(body.path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"deleted": body.path}


# ── Audit Log ─────────────────────────────────────────────────────────────────

@router.get("/audit")
def get_audit_log(page: int = 1, limit: int = 50, intent: str = ""):
    """
    Paginated audit log from capstone.logging.interaction_logs.
    Filter by intent by passing ?intent=answer_seeking (or curriculum / off_topic).
    """
    offset = (page - 1) * limit
    intent_filter = f"AND intent = '{intent}'" if intent else ""

    rows = _run_sql(f"""
        SELECT log_id, session_id, timestamp, user_input, system_output, intent, attempt
        FROM interaction_logs
        WHERE 1=1 {intent_filter}
        ORDER BY timestamp DESC
        LIMIT {limit} OFFSET {offset}
    """)

    count_rows = _run_sql(f"""
        SELECT COUNT(*) FROM interaction_logs WHERE 1=1 {intent_filter}
    """)

    entries = [
        {
            "log_id": r[0],
            "session_id": r[1],
            "timestamp": r[2],
            "user_input": r[3],
            "system_output": r[4],
            "intent": r[5],
            "attempt": int(r[6]) if r[6] else 1,
        }
        for r in rows
    ]

    return {
        "entries": entries,
        "total": int(count_rows[0][0]) if count_rows and count_rows[0][0] else 0,
        "page": page,
        "limit": limit,
    }
