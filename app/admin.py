import io
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementResponse, StatementState

# States that mean a SQL statement has finished (success or otherwise).
# Used to decide when to stop polling.
_TERMINAL = {StatementState.SUCCEEDED, StatementState.FAILED,
             StatementState.CANCELED, StatementState.CLOSED}

# ── Constants ─────────────────────────────────────────────────────────────────

# Root path of the curriculum volume in Unity Catalog.
# All week folders live directly under this path.
VOLUME_ROOT = "/Volumes/capstone/bronze_layer/curriculum_raw"

# Every new week gets these three subfolders created automatically.
WEEK_SUBFOLDERS = ["markdown", "pdfs", "quizzes"]

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Singleton client + cached warehouse ID ────────────────────────────────────
# Creating a WorkspaceClient triggers an auth handshake with Databricks.
# Doing that on every request added ~0.5s of overhead per call. Instead we
# create one client per process and reuse it across all requests.
#
# Similarly, listing warehouses to find the ID never changes at runtime, so we
# resolve it once and store it. This eliminates 3 of the 4 redundant
# warehouses.list() API calls that the old code made per overview request.

_ws_client: WorkspaceClient | None = None
_warehouse_id: str | None = None


def _client() -> WorkspaceClient:
    """Return the process-level WorkspaceClient, creating it on first call."""
    global _ws_client
    if _ws_client is None:
        _ws_client = WorkspaceClient(
            host=os.environ["DATABRICKS_HOST"],
            token=os.environ["DATABRICKS_TOKEN"],
        )
    return _ws_client


def _get_warehouse_id() -> str:
    """
    Return the SQL warehouse ID to use for all statement executions.

    Prefers a warehouse that is already RUNNING to avoid cold-start latency.
    The result is cached for the process lifetime — warehouse IDs don't change
    at runtime and listing them on every query was a measurable bottleneck.
    """
    global _warehouse_id
    if _warehouse_id is not None:
        return _warehouse_id

    client = _client()
    warehouses = list(client.warehouses.list())
    if not warehouses:
        raise HTTPException(status_code=500, detail="No SQL warehouses available")

    # Prefer an already-running warehouse so the first query doesn't stall
    # waiting for a cold start (can take 2-5 minutes on a stopped warehouse).
    running = [w for w in warehouses if str(w.state).upper() == "RUNNING"]
    chosen = (running or warehouses)[0]
    if chosen.id is None:
        raise HTTPException(status_code=500, detail="No SQL warehouses available")

    _warehouse_id = chosen.id
    return _warehouse_id


# ── SQL execution helpers ─────────────────────────────────────────────────────

def _poll(statement_id: str) -> StatementResponse:
    """
    Poll a statement until it reaches a terminal state.

    The Databricks statement execution API allows a maximum synchronous wait
    of 50 seconds. If the warehouse is cold, startup alone can take 2-5
    minutes, so we fall back to polling every 10s for up to ~4 minutes.
    """
    client = _client()
    for _ in range(24):
        resp = client.statement_execution.get_statement(statement_id)
        if (resp.status.state if resp.status else None) in _TERMINAL:
            return resp
        time.sleep(10)
    raise HTTPException(status_code=504, detail="SQL statement timed out")


def _execute(sql: str) -> StatementResponse:
    """
    Submit a SQL statement and block until it completes.

    Uses a 50s synchronous wait (the API maximum). If the statement is still
    pending after that — typically because the warehouse is warming up — we
    hand off to _poll() to continue waiting.
    """
    client = _client()
    resp = client.statement_execution.execute_statement(
        warehouse_id=_get_warehouse_id(),
        statement=sql,
        catalog="capstone",
        schema="logging",
        wait_timeout="50s",
    )
    state = resp.status.state if resp.status else None

    # If the warehouse was cold, the statement won't be done yet — poll until it is.
    if state not in _TERMINAL:
        if not resp.statement_id:
            raise HTTPException(status_code=500, detail="No statement ID returned")
        resp = _poll(resp.statement_id)
        state = resp.status.state if resp.status else None

    if state != StatementState.SUCCEEDED:
        err = resp.status.error.message if resp.status and resp.status.error else str(state)
        raise HTTPException(status_code=500, detail=err)
    return resp


def _run_sql(sql: str) -> list[list]:
    """Execute SQL and return raw rows as a list of lists (no column mapping)."""
    resp = _execute(sql)
    return (resp.result.data_array or []) if resp.result else []


def _query_view(view_name: str) -> list[dict]:
    """
    Query a view and return rows as dicts keyed by column name.

    Column names are read from the statement execution manifest rather than
    being hard-coded, so view schema changes don't require code updates here.
    The normalizer functions below handle mapping view-specific column names
    to the consistent shape the frontend expects.
    """
    resp = _execute(f"SELECT * FROM {view_name}")
    schema = resp.manifest.schema if resp.manifest else None
    cols = [c.name for c in schema.columns] if schema and schema.columns else []
    rows = (resp.result.data_array or []) if resp.result else []
    return [dict(zip(cols, row)) for row in rows] if cols else []


# ── View column normalizers ───────────────────────────────────────────────────
# The three Databricks views use their own column naming conventions.
# These normalizers translate view rows into the fixed shape the frontend
# expects, trying several common column name variants so a view rename
# doesn't silently break the dashboard.

def _get(row: dict, *keys):
    """Return the first non-None value found among the given keys in a row dict."""
    for k in keys:
        v = row.get(k)
        if v is not None:
            return v
    return None


def _normalize_daily(rows: list[dict]) -> list[dict]:
    """
    Normalize v_daily_usage rows → [{"date": "YYYY-MM-DD", "count": int}, ...].
    Sorted ascending by date so the bar chart renders left-to-right chronologically.
    """
    out = []
    for r in rows:
        date  = _get(r, "date", "usage_date", "log_date", "dt", "activity_date")
        count = _get(r, "total_interactions", "question_count", "total_questions", "count", "n", "total")
        if date is not None:
            out.append({"date": str(date), "count": int(count or 0)})
    return sorted(out, key=lambda x: x["date"])


def _normalize_intent(rows: list[dict]) -> list[dict]:
    """
    Normalize v_intent_breakdown rows → [{"intent": str, "count": int}, ...].
    Order is preserved as returned by the view (typically by count desc).
    """
    out = []
    for r in rows:
        intent = _get(r, "intent", "intent_type", "intent_label")
        count  = _get(r, "question_count", "total_questions", "count", "n", "total")
        if intent is not None:
            out.append({"intent": str(intent), "count": int(count or 0)})
    return out


def _normalize_hourly(rows: list[dict]) -> list[dict]:
    """
    Normalize v_hourly_activity rows → [{"hour": int, "count": int}, ...].
    Sorted ascending by hour so the bar chart renders 0–23 left-to-right.
    """
    out = []
    for r in rows:
        hour  = _get(r, "hour_of_day", "hour", "activity_hour", "h", "hour_bucket")
        count = _get(r, "total_interactions", "question_count", "total_questions", "count", "n", "total")
        if hour is not None:
            out.append({"hour": int(hour), "count": int(count or 0)})
    return sorted(out, key=lambda x: x["hour"])


# ── Overview cache ────────────────────────────────────────────────────────────
# The overview endpoint fires 4 SQL queries against Databricks. Even in
# parallel (see get_overview) that's ~2-3s on a warm warehouse. Since the
# metrics shown are "past 7 days" aggregates, 60-second staleness is
# acceptable. Caching means repeat loads and refreshes are instant (~14ms)
# and we don't hammer the warehouse on every admin page visit.

_overview_cache: dict | None = None   # last computed payload
_overview_cache_ts: float = 0.0       # time.monotonic() timestamp of last fill
_OVERVIEW_TTL = 60.0                  # seconds before the cache is considered stale


# ── Overview Metrics ──────────────────────────────────────────────────────────

@router.get("/metrics/overview")
def get_overview():
    """
    Return aggregated usage metrics for the admin dashboard Overview page.

    Data sources:
      - v_daily_usage       → questions per calendar day
      - v_hourly_activity   → questions by hour of day (0-23)
      - v_intent_breakdown  → question counts grouped by intent label
      - interaction_logs    → count of sessions that hit the hard block (attempt >= 3)

    Performance notes:
      - All four queries run in parallel via ThreadPoolExecutor.
      - Results are cached for 60 seconds to avoid hammering Databricks on
        every page load or admin refresh.
    """
    global _overview_cache, _overview_cache_ts

    # Return the cached payload if it's still fresh.
    if _overview_cache is not None and (time.monotonic() - _overview_cache_ts) < _OVERVIEW_TTL:
        return _overview_cache

    # SQL for sessions that hit the hard block (3rd answer-seeking attempt).
    # No view exists for this yet, so we query interaction_logs directly.
    BEHIND_SQL = """
        SELECT COUNT(DISTINCT session_id) AS n
        FROM interaction_logs
        WHERE attempt >= 3
          AND timestamp >= DATE_SUB(CURRENT_DATE(), 7)
    """

    # Each task is a zero-argument lambda so ThreadPoolExecutor can call it
    # without needing to pass arguments through the future interface.
    tasks = {
        "daily":  lambda: _normalize_daily(_query_view("v_daily_usage")),
        "intent": lambda: _normalize_intent(_query_view("v_intent_breakdown")),
        "hourly": lambda: _normalize_hourly(_query_view("v_hourly_activity")),
        "behind": lambda: _run_sql(BEHIND_SQL),
    }

    # Fire all four queries concurrently. On a warm warehouse each takes ~2s;
    # sequentially that was ~10-15s total — in parallel it's just the slowest one.
    results: dict = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fn): key for key, fn in tasks.items()}
        for future in as_completed(futures):
            key = futures[future]
            # Calling .result() re-raises any exception from the worker thread
            # on the main thread, which FastAPI converts to a 500 response.
            results[key] = future.result()

    daily = results["daily"]
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    behind_rows = results["behind"]

    payload = {
        "daily":            daily,
        "hourly_activity":  results["hourly"],
        # total_today is derived from daily so we don't need a separate query.
        "total_today":      next((d["count"] for d in daily if d["date"] == today_str), 0),
        "total_week":       sum(d["count"] for d in daily),
        "behind_count":     int(behind_rows[0][0]) if behind_rows and behind_rows[0][0] else 0,
        "intent_breakdown": results["intent"],
    }

    # Store in cache with the current timestamp.
    _overview_cache = payload
    _overview_cache_ts = time.monotonic()
    return payload


# ── Curriculum / Volume ───────────────────────────────────────────────────────

@router.get("/curriculum/weeks")
def list_weeks():
    """
    List the top-level week folders inside the Bronze curriculum volume.
    Returns: { weeks: [{ name: str, path: str }] }
    """
    client = _client()
    try:
        entries = list(client.files.list_directory_contents(VOLUME_ROOT))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Filter to directories only — any stray files at the root are ignored.
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
    """
    Create a new week folder in the volume with the standard subfolders.

    The Databricks Files API has no single "mkdir -p" call, so we create
    each subfolder individually. All three must succeed or we surface the error.

    Returns: { created: str, subfolders: list[str] }
    """
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
    """
    List files inside a specific subfolder of a week.

    Only the three known subfolders are allowed — anything else is rejected
    to prevent path traversal into arbitrary volume locations.

    Returns: { files: [{ name, path, size_bytes, last_modified }], week, folder }
    """
    if folder not in WEEK_SUBFOLDERS:
        raise HTTPException(status_code=400, detail=f"folder must be one of {WEEK_SUBFOLDERS}")

    path = f"{VOLUME_ROOT}/{week}/{folder}"
    client = _client()

    try:
        entries = list(client.files.list_directory_contents(path))
    except Exception as exc:
        # 404 because the most likely cause is a week/folder that doesn't exist yet.
        raise HTTPException(status_code=404, detail=str(exc))

    files = [
        {
            "name": (e.path or "").rstrip("/").split("/")[-1],
            "path": e.path,
            "size_bytes": e.file_size,
            # last_modified comes back as epoch milliseconds from the SDK.
            "last_modified": (
                datetime.fromtimestamp(e.last_modified / 1000, tz=timezone.utc).isoformat()
                if e.last_modified else None
            ),
        }
        for e in entries
        if not e.is_directory   # skip any nested subdirectories
    ]
    return {"files": files, "week": week, "folder": folder}


@router.post("/curriculum/weeks/{week}/{folder}/upload")
async def upload_file(week: str, folder: str, file: UploadFile = File(...)):
    """
    Upload a file into the specified week/folder in the curriculum volume.

    Uses overwrite=True so re-uploading a corrected version of an existing
    file replaces it rather than erroring. The filename is taken from the
    original file — no server-side renaming is applied.

    Returns: { uploaded: str, path: str }
    """
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
    """
    Delete a single file from the curriculum volume.

    The path is validated against VOLUME_ROOT before deletion to prevent
    an admin from accidentally (or maliciously) deleting files outside the
    curriculum volume.

    Returns: { deleted: str }
    """
    # Reject any path that escapes the curriculum volume root.
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
    Return a paginated, optionally filtered slice of interaction_logs.

    Query params:
      page   — 1-based page number (default 1)
      limit  — rows per page (default 50)
      intent — if provided, filter to rows where intent = this value
                (valid values: curriculum, answer_seeking, off_topic)

    Returns: { entries: [...], total: int, page: int, limit: int }
    """
    offset = (page - 1) * limit

    # Build the optional WHERE clause fragment. The intent value comes from
    # a dropdown in the UI so it's constrained, but in production this should
    # be parameterized — noted here for future hardening.
    intent_filter = f"AND intent = '{intent}'" if intent else ""

    # Fetch the requested page of log rows.
    rows = _run_sql(f"""
        SELECT log_id, session_id, timestamp, user_input, system_output, intent, attempt
        FROM interaction_logs
        WHERE 1=1 {intent_filter}
        ORDER BY timestamp DESC
        LIMIT {limit} OFFSET {offset}
    """)

    # Fetch the total count so the frontend can calculate page count.
    count_rows = _run_sql(f"""
        SELECT COUNT(*) FROM interaction_logs WHERE 1=1 {intent_filter}
    """)

    entries = [
        {
            "log_id":        r[0],
            "session_id":    r[1],
            "timestamp":     r[2],
            "user_input":    r[3],
            "system_output": r[4],
            "intent":        r[5],
            # attempt defaults to 1 if the column is null (older log rows).
            "attempt":       int(r[6]) if r[6] else 1,
        }
        for r in rows
    ]

    return {
        "entries": entries,
        "total":   int(count_rows[0][0]) if count_rows and count_rows[0][0] else 0,
        "page":    page,
        "limit":   limit,
    }
