import io
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementResponse, StatementState

logger = logging.getLogger(__name__)

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

# Per-folder allowlist for upload validation. Each folder is bound to a single
# content kind, and the downstream silver chunker keys off both the folder
# segment (via _parse_volume_path → content_type) AND the file extension when
# reading the file contents. Letting a .pdf land in markdown/ would silently
# break the chunker (it tries to open and string-decode the bytes), so the
# guard runs at the upload boundary rather than discovering the mismatch in
# the ETL job an hour later.
#
# We accept both .md and .markdown for the markdown folder because both are
# in common use and the chunker is extension-agnostic once the file is opened.
# Quizzes are JSON-only — the chunker parses them with json.loads().
FOLDER_ALLOWED_EXTENSIONS: dict[str, set[str]] = {
    "markdown": {".md", ".markdown"},
    "pdfs":     {".pdf"},
    "quizzes":  {".json"},
}

# Silver / vector / semantic layer object names — referenced by the cascade
# delete flow when a file is removed from the bronze volume. Keeping these as
# module-level constants (not inlined into the SQL strings) makes it easy to
# point a non-prod deployment at a different catalog/schema later by patching
# this single block, and lets the test suite assert against well-known names.
#
# Layer ownership:
#   SILVER_TABLE     — chunked + metadata-enriched rows from the chunking notebook
#   VECTOR_TABLE     — Delta source table for the vector search index (CDC on)
#   VECTOR_ENDPOINT  — the Vector Search compute endpoint serving the index
#   VECTOR_INDEX     — the Delta Sync index (TRIGGERED pipeline; needs .sync())
SILVER_TABLE    = "capstone.silver_layer.curriculum_chunks"
VECTOR_TABLE    = "capstone.vector_layer.capstone_vector_store"
VECTOR_ENDPOINT = "capstone_vector_endpoint"
VECTOR_INDEX    = "capstone.vector_layer.curriculum_semantic_index"

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
# VectorSearchClient — typed as Any because importing the type at module load
# would defeat the lazy-import savings below. Materialized on first call to
# _vector_client() and reused for the process lifetime.
_vs_client = None


def _client() -> WorkspaceClient:
    """Return the process-level WorkspaceClient, creating it on first call."""
    global _ws_client
    if _ws_client is None:
        _ws_client = WorkspaceClient(
            host=os.environ["DATABRICKS_HOST"],
            token=os.environ["DATABRICKS_TOKEN"],
        )
    return _ws_client


def _vector_client():
    """
    Return the process-level VectorSearchClient, creating it on first call.

    The vectorsearch SDK is imported lazily because:
      1. It pulls in heavy transitive deps (mlflow, grpc, etc.) — importing it
         eagerly at module load slows down every endpoint, even the ones that
         never touch vector search.
      2. Only the cascade delete and (potentially) future endpoints need it,
         so most admin-page requests never pay this cost.

    `disable_notice=True` suppresses the SDK's "Hello! Welcome to Vector Search"
    banner that otherwise prints to stdout on every client instantiation —
    useful for local debugging but noise in server logs.
    """
    global _vs_client
    if _vs_client is None:
        from databricks.vector_search.client import VectorSearchClient
        _vs_client = VectorSearchClient(disable_notice=True)
    return _vs_client


def _sql_escape(value: str) -> str:
    """
    Escape single quotes for safe inclusion in a SQL string literal.

    The Databricks statement execution API supports parameterized queries, but
    the existing _execute() helper doesn't thread parameters through yet, and
    every other call site in this file builds SQL by f-string interpolation.
    Until that helper is upgraded, this one-liner is the local guard against
    apostrophes in filenames (e.g. ``o'reilly_notes.md``) breaking the query
    or — worse — being interpreted as injection.
    """
    return value.replace("'", "''")


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

    Two-stage validation before we touch the volume:

      1. Folder must be one of the three known subfolders. The route already
         pins this in the URL, but we still check explicitly so a typo'd path
         in a curl test produces a clean 400 instead of an internal error
         later in the chunker.

      2. File extension must match the folder's allowlist
         (see FOLDER_ALLOWED_EXTENSIONS). PDFs cannot land in markdown/, JSON
         quizzes cannot land in pdfs/, etc. This guard exists for two reasons:
           - The silver chunker dispatches on the folder name AND opens the
             file with assumptions about its format. A misrouted file would
             not error at upload time but would crash (or silently produce
             garbage chunks) during the ETL run.
           - The file-arrival-triggered job watches the entire bronze volume,
             so a mistake here doesn't fail loudly — it pollutes silver until
             someone notices and runs reconciliation.

    Uses overwrite=True so re-uploading a corrected version of an existing
    file replaces it rather than erroring. The filename is taken from the
    original file — no server-side renaming is applied.

    Returns: { uploaded: str, path: str }
    """
    if folder not in WEEK_SUBFOLDERS:
        raise HTTPException(status_code=400, detail=f"folder must be one of {WEEK_SUBFOLDERS}")

    # Extension check is case-insensitive ("Notes.MD" is still markdown).
    # os.path.splitext returns ("Notes", ".MD"); .lower() normalizes for the
    # set membership check against the allowlist.
    filename = file.filename or ""
    _stem, ext = os.path.splitext(filename)
    ext = ext.lower()
    allowed = FOLDER_ALLOWED_EXTENSIONS[folder]
    if ext not in allowed:
        # Sorted for stable error messages — useful both for tests and for
        # admins reading the toast in the UI.
        allowed_str = ", ".join(sorted(allowed))
        raise HTTPException(
            status_code=400,
            detail=(
                f"File '{filename}' has extension '{ext or '(none)'}', "
                f"which is not allowed in {folder}/. "
                f"Allowed extensions for this folder: {allowed_str}."
            ),
        )

    content = await file.read()
    path = f"{VOLUME_ROOT}/{week}/{folder}/{filename}"

    client = _client()
    try:
        client.files.upload(file_path=path, contents=io.BytesIO(content), overwrite=True)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # The file-arrival-triggered ETL job picks up the new file ~30s after
    # upload (file_arrival.wait_after_last_change_seconds) and runs silver
    # chunking + vector sync. Status of that run is visible in the Databricks
    # Jobs UI; we don't surface it here to keep the upload response shape
    # stable and the UI flow simple.
    return {"uploaded": filename, "path": path}


class DeleteFileRequest(BaseModel):
    path: str


def _parse_volume_path(path: str) -> tuple[str, str, str]:
    """
    Split a bronze volume path into (week, folder, filename).

    Example:
        /Volumes/capstone/bronze_layer/curriculum_raw/week_01/markdown/intro.md
        -> ("week_01", "markdown", "intro.md")

    Falls back to empty strings for any segment we can't identify so the caller
    can decide whether the fallback path is usable. Specifically, the vector
    cleanup fallback in delete_file() needs BOTH `week` and `filename` to
    disambiguate (two weeks can both contain a file named `intro.md`); when
    either is empty, the fallback is skipped rather than over-deleting.

    Note: we intentionally do not use pathlib.Path here because the volume
    path is a stable, forward-slash UC path — not the local filesystem — and
    Path() would normalize/lose information on Windows runtimes.
    """
    # Strip the well-known volume root prefix so the remaining parts are
    # exactly [week, folder, filename] in the standard curriculum layout.
    rel = path[len(VOLUME_ROOT):].lstrip("/")
    parts = rel.split("/")
    week     = parts[0]  if len(parts) > 0 else ""
    folder   = parts[1]  if len(parts) > 1 else ""
    filename = parts[-1] if parts            else ""
    return week, folder, filename


def _trigger_index_sync() -> bool:
    """
    Fire the vector index sync in a background thread (fire-and-forget).

    Why this isn't inline in the request handler:
      - The vector search index is configured as a TRIGGERED Delta Sync index
        (see "Capstone to Vector DB Sync.ipynb"). It doesn't auto-pull CDC
        changes from the source Delta table — we have to call .sync() to kick
        an incremental update.
      - Sync latency for a small change is typically 20-60s, occasionally
        longer if the index is warming up. Blocking the HTTP response on it
        would mean the admin UI sits on a spinner for a minute every delete,
        even though the bronze file is already gone and the silver/vector
        deltas are already committed.
      - From the user's perspective, the file disappears from the file list
        the moment this function returns. The retrieval layer might briefly
        still surface the deleted chunks (worst case: until the next sync
        completes), which is acceptable for this hackathon and can be tightened
        later with a wait-for-sync flag if needed.

    Failures inside the background thread are logged but don't surface to the
    user — the silver/vector tables are already cleaned, so the deleted chunks
    won't come back. A failed sync just means the embedded copies stick around
    until the next successful sync (or the next manual trigger).

    Returns True if the background thread was successfully dispatched, False
    if we couldn't even start the thread (extremely rare — would indicate an
    OS resource exhaustion).
    """
    def _run():
        # This runs off the request thread, so any exception here must NOT be
        # allowed to propagate (it would crash silently in a background worker
        # and leave no trace beyond stderr). Log + swallow.
        try:
            index = _vector_client().get_index(
                endpoint_name=VECTOR_ENDPOINT,
                index_name=VECTOR_INDEX,
            )
            index.sync()
        except Exception as exc:
            logger.warning("Vector index sync failed: %s", exc)

    try:
        # daemon=True so the thread doesn't keep the process alive at shutdown.
        # A delete cascade is recoverable on the next sync, so we'd rather drop
        # an in-flight sync than block process exit.
        threading.Thread(target=_run, daemon=True).start()
        return True
    except Exception as exc:
        logger.warning("Could not dispatch vector index sync: %s", exc)
        return False


@router.delete("/curriculum/file")
def delete_file(body: DeleteFileRequest):
    """
    Cascade-delete a curriculum file across all four data layers.

    Layer order and the reasoning behind each step:

      1. Silver lookup — fetch the chunk_ids that belong to this file BEFORE
                         touching anything. If the silver DELETE in step 3
                         raced with another writer (e.g. a re-ingest job),
                         we'd lose the ids needed to drive the vector
                         cleanup in step 4. Looking up first decouples the
                         vector cleanup from the silver delete order.
      2. Bronze       — remove the raw file from the UC volume. Doing this
                         second (not first) means a SQL warehouse outage
                         won't leave the bronze gone but silver/vector
                         intact. The UI's "deleting" toast already shows
                         intent, and re-clicking remove on an in-flight or
                         partially-failed delete is idempotent (see the
                         NOT_FOUND handling below).
      3. Silver       — DELETE rows by source_path. Using full path (not
                         filename) handles the case where two weeks both
                         contain a file with the same name.
      4. Vector store — DELETE rows from the vector source Delta table by
                         id IN (...). Falls back to a JSON metadata match
                         on (source_file, week) if silver returned no
                         chunk_ids — covers the edge case where silver was
                         rebuilt or never populated, but the vector table
                         still holds the orphaned chunks.
      5. Semantic     — Fire .sync() on the TRIGGERED Delta Sync index in a
                         background thread. CDC on the vector source table
                         drives the actual delete on the embedded copy.

    Idempotency: re-clicking remove on a file that's already partially gone
    is safe. NOT_FOUND on bronze is treated as success; silver/vector DELETEs
    on already-empty result sets are no-ops at the SQL level.

    Security: the path is validated against VOLUME_ROOT to prevent the
    endpoint from being weaponized to delete files elsewhere in UC. The SQL
    interpolation is hardened with _sql_escape() against apostrophe-containing
    filenames (see the helper's docstring for why we're not parameterizing yet).

    Returns:
        {
          deleted: str,               # echo of the input path
          silver_rows: int,           # how many chunk rows were on this file
          vector_rows: int,           # how many vector_store rows were deleted
                                      # (0 if the fallback path ran — see below)
          index_sync_triggered: bool, # whether the background sync dispatched
        }
    """
    # ── Guard rail: never let this endpoint touch paths outside the curriculum
    # volume. The bronze workspace contains other UC objects (logging tables,
    # checkpoints, etc.) that an admin should NOT be able to nuke via a curl
    # against this endpoint.
    if not body.path.startswith(VOLUME_ROOT):
        raise HTTPException(status_code=400, detail="Path is outside the curriculum volume")

    # Bind locals up-front so every step below has consistent inputs and the
    # SQL-safe literal isn't recomputed each time.
    path     = body.path
    path_lit = _sql_escape(path)
    week, _folder, filename = _parse_volume_path(path)

    # ── Step 1: collect chunk_ids from silver before deleting anything ────────
    # The vector_store rows are keyed by chunk_id (= silver's chunk_id), so we
    # need this list to drive the vector DELETE in step 4. Two reasons we do
    # the SELECT before the DELETE rather than relying on a single statement:
    #   - The Databricks SQL DELETE doesn't return the affected row keys, only
    #     a count. We need the actual ids.
    #   - Capturing the ids first means a concurrent re-ingest writer can't
    #     race us into a state where silver is half-empty by the time we read.
    # A SELECT failure here is recoverable: we fall back to the filename+week
    # JSON match in step 4, so silver being temporarily unreachable doesn't
    # block the rest of the cascade.
    try:
        chunk_rows = _run_sql(
            f"SELECT chunk_id FROM {SILVER_TABLE} WHERE source_path = '{path_lit}'"
        )
    except HTTPException:
        chunk_rows = []
    chunk_ids = [r[0] for r in chunk_rows if r and r[0]]

    # ── Step 2: delete bronze file ───────────────────────────────────────────
    # This is the only step the user-facing UI directly observes (the file
    # row vanishes from the listing). A failure here aborts the cascade so we
    # don't leave silver/vector half-cleaned for a file the admin can still
    # see — they'd have no UI affordance to retry against the missing bronze.
    #
    # NOT_FOUND is the deliberate exception: re-clicking "remove" on a file
    # whose bronze copy is already gone (e.g. a previous cascade succeeded on
    # bronze/silver but failed on vector) should still finish cleaning up the
    # downstream layers.
    client = _client()
    try:
        client.files.delete(path)
    except Exception as exc:
        msg = str(exc).lower()
        # The SDK doesn't expose a typed NOT_FOUND exception, so we sniff the
        # message. Three known surfaces: REST 404, "FILE_NOT_FOUND" error code,
        # "not found" phrasing. Match all three to be defensive.
        if "not_found" not in msg and "not found" not in msg and "404" not in msg:
            raise HTTPException(status_code=500, detail=f"Bronze delete failed: {exc}")

    # ── Step 3: delete silver rows ───────────────────────────────────────────
    # We already know the row count from step 1, so we can report silver_rows
    # without doing a follow-up COUNT(*). A DELETE failure here is the worst
    # cascade state to be in: bronze is gone but silver still holds chunks
    # that reference a missing source file. We surface that explicitly in the
    # error detail so the admin knows reconciliation is needed.
    silver_rows = 0
    try:
        _execute(f"DELETE FROM {SILVER_TABLE} WHERE source_path = '{path_lit}'")
        silver_rows = len(chunk_ids)
    except HTTPException as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Bronze deleted but silver cleanup failed: {exc.detail}",
        )

    # ── Step 4: delete vector store rows ─────────────────────────────────────
    # Two paths:
    #   - Primary: we have chunk_ids from silver, so we can do a precise
    #     `id IN (...)` delete. This is the common case and lets us report
    #     an accurate vector_rows count.
    #   - Fallback: silver returned nothing (either step 1 errored, or the
    #     silver table has no rows for this path even though the vector
    #     table does — a real possibility if silver was rebuilt without
    #     re-running the vector sync notebook). We match on the JSON
    #     metadata fields the sync notebook packs into each vector row.
    #     vector_rows stays 0 because we'd need a separate SELECT to know
    #     how many were actually affected — the index sync in step 5 will
    #     reconcile regardless.
    vector_rows = 0
    try:
        if chunk_ids:
            # Quote each id individually so the IN-list is bulletproof against
            # any id containing characters that happen to confuse SQL parsing.
            id_list = ", ".join(f"'{_sql_escape(cid)}'" for cid in chunk_ids)
            _execute(f"DELETE FROM {VECTOR_TABLE} WHERE id IN ({id_list})")
            vector_rows = len(chunk_ids)
        elif filename and week:
            # Fallback only fires when we have BOTH filename and week — that's
            # the minimum signal needed to disambiguate "intro.md in week_01"
            # from "intro.md in week_02" without over-deleting.
            fname_lit = _sql_escape(filename)
            week_lit  = _sql_escape(week)
            _execute(
                f"DELETE FROM {VECTOR_TABLE} "
                f"WHERE get_json_object(metadata, '$.source_file') = '{fname_lit}' "
                f"  AND get_json_object(metadata, '$.week') = '{week_lit}'"
            )
    except HTTPException as exc:
        # By this point bronze + silver are already clean. A vector failure
        # leaves orphaned embeddings that the index sync will keep serving
        # until manually reconciled, so surface explicitly.
        raise HTTPException(
            status_code=500,
            detail=f"Bronze + silver cleared but vector cleanup failed: {exc.detail}",
        )

    # ── Step 5: trigger the semantic index sync (fire-and-forget) ────────────
    # See _trigger_index_sync() for why this runs off-thread and why a failure
    # here is intentionally non-fatal.
    index_sync_triggered = _trigger_index_sync()

    return {
        "deleted": path,
        "silver_rows": silver_rows,
        "vector_rows": vector_rows,
        "index_sync_triggered": index_sync_triggered,
    }


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
