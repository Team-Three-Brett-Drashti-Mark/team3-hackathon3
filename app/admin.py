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
# Curriculum-ETL job ID. Resolved on first upload by searching the workspace
# for the deployed job (see _get_etl_job_id below), then cached for the
# process lifetime since the job ID is stable once the Asset Bundle is
# deployed. Reset to None if the upload-triggered run_now fails — that's
# usually the signal that the job was renamed or redeployed.
_etl_job_id: int | None = None


def _client() -> WorkspaceClient:
    """Return the process-level WorkspaceClient, creating it on first call."""
    global _ws_client
    if _ws_client is None:
        _ws_client = WorkspaceClient(
            host=os.environ["DATABRICKS_HOST"],
            token=os.environ["DATABRICKS_TOKEN"],
            auth_type="pat",
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


def _get_etl_job_id() -> int:
    """
    Return the curriculum ETL job ID, resolving it on first call.

    The job is created by `databricks bundle deploy` (see
    resources/curriculum_etl.yml) and named like:
        "[dev w_brett_coleman] [dev] Curriculum ETL"
    The username/target prefix differs per developer/environment, so we
    can't hardcode the full name — we filter by the trailing "Curriculum
    ETL" segment, which is set by the bundle resource key.

    Allows an explicit override via the CURRICULUM_ETL_JOB_ID env var. That
    knob exists for two reasons:
      1. A future migration to a service-principal deploy where the bundle
         name suffix changes.
      2. Local debugging where you want to point at a specific job ID
         without re-deploying.

    Raises HTTPException(500) if no matching job is found — the upload path
    catches and degrades to "uploaded but no ETL run started", so the file
    still lands in bronze even if the job can't be found.
    """
    global _etl_job_id
    if _etl_job_id is not None:
        return _etl_job_id

    override = os.environ.get("CURRICULUM_ETL_JOB_ID")
    if override:
        try:
            _etl_job_id = int(override)
            return _etl_job_id
        except ValueError:
            # Bad env var — fall through to workspace lookup rather than
            # crashing the whole upload flow on a typo.
            logger.warning("CURRICULUM_ETL_JOB_ID is not an int: %r", override)

    client = _client()
    # jobs.list() returns BaseJob objects with .job_id and .settings.name.
    # We expect O(10s) of jobs in this workspace so a full list scan is fine;
    # if this grows to 100s, switch to a server-side name filter.
    for job in client.jobs.list():
        name = (job.settings.name if job.settings else "") or ""
        if name.endswith("Curriculum ETL"):
            if job.job_id is None:
                continue
            _etl_job_id = job.job_id
            logger.info("Resolved curriculum ETL job: id=%d name=%r",
                        _etl_job_id, name)
            return _etl_job_id

    raise HTTPException(
        status_code=500,
        detail=(
            "No curriculum ETL job found in the workspace. "
            "Run `databricks bundle deploy` to create it."
        ),
    )


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
        raise HTTPException(status_code=500, detail="No SQL warehouse ID available")

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
    now = time.monotonic()
    if _overview_cache is not None and (now - _overview_cache_ts) < _OVERVIEW_TTL:
        return _overview_cache

    def _fetch_daily():
        return _normalize_daily(_query_view("v_daily_usage"))

    def _fetch_intent():
        return _normalize_intent(_query_view("v_intent_breakdown"))

    def _fetch_hourly():
        return _normalize_hourly(_query_view("v_hourly_activity"))

    def _fetch_behind():
        # Sessions that reached attempt 3+ in the last 7 days.
        rows = _run_sql(
            """
            SELECT COUNT(DISTINCT session_id) AS n
            FROM interaction_logs
            WHERE attempt >= 3
              AND timestamp >= DATE_SUB(CURRENT_DATE(), 7)
            """
        )
        return int(rows[0][0] or 0) if rows else 0

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(_fetch_daily):  "daily",
            pool.submit(_fetch_intent): "intent",
            pool.submit(_fetch_hourly): "hourly",
            pool.submit(_fetch_behind): "behind",
        }

        results = {}
        for fut in as_completed(futures):
            key = futures[fut]
            try:
                results[key] = fut.result()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Overview metric fetch failed for %s", key)
                raise HTTPException(
                    status_code=500,
                    detail=f"Overview metric '{key}' failed: {type(exc).__name__}: {exc}",
                ) from exc

    daily = results["daily"]
    overview = {
        "daily": daily,
        "hourly_activity": results["hourly"],
        # "today" = most recent day in the daily series. This avoids timezone drift
        # between the SQL view and the app server and matches what the chart shows.
        "total_today": daily[-1]["count"] if daily else 0,
        # The stat card label says "Total questions asked". Keep this as the total
        # across all days returned by the view (typically last 7 days), not just 7.
        "total_week": sum(d["count"] for d in daily),
        "behind_count": results["behind"],
        "intent_breakdown": results["intent"],
    }

    # Cache the freshly computed payload.
    _overview_cache = overview
    _overview_cache_ts = now
    return overview


class CreateWeekRequest(BaseModel):
    week_name: str


class DeleteFileRequest(BaseModel):
    path: str


def _week_path(week_name: str) -> str:
    # Basic normalization: spaces → underscores, strip leading/trailing slashes.
    safe = week_name.strip().replace(" ", "_")
    if not safe:
        raise HTTPException(status_code=400, detail="Week name is required")
    return f"{VOLUME_ROOT}/{safe}"


def _list_dir(path: str):
    client = _client()
    try:
        return list(client.files.list_directory_contents(path))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"List failed for {path}: {exc}") from exc


@router.get("/curriculum/weeks")
def list_weeks():
    entries = _list_dir(VOLUME_ROOT)
    weeks = []
    for e in entries:
        if getattr(e, "is_directory", False):
            weeks.append({"name": e.name, "path": e.path})
    weeks.sort(key=lambda w: w["name"])
    return {"weeks": weeks}


@router.post("/curriculum/weeks")
def create_week(req: CreateWeekRequest):
    client = _client()
    week_root = _week_path(req.week_name)

    try:
        client.files.create_directory(week_root)
        for sub in WEEK_SUBFOLDERS:
            client.files.create_directory(f"{week_root}/{sub}")
        return {"created": True, "path": week_root}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Create week failed: {exc}") from exc


@router.get("/curriculum/weeks/{week_name}/{folder_name}")
def list_folder_files(week_name: str, folder_name: str):
    folder_path = f"{_week_path(week_name)}/{folder_name}"
    entries = _list_dir(folder_path)
    files = []
    for e in entries:
        if not getattr(e, "is_directory", False):
            files.append(
                {
                    "name": e.name,
                    "path": e.path,
                    "size_bytes": getattr(e, "file_size", None),
                    "last_modified": getattr(e, "last_modified", None),
                }
            )
    files.sort(key=lambda f: f["name"])
    return {"files": files}


def _parse_volume_path(volume_path: str) -> tuple[str, str, str, str, str]:
    """
    Parse a curriculum bronze volume path into its semantic pieces.

    Input shape (enforced):
        /Volumes/<catalog>/<schema>/<volume>/<week>/<folder>/<file>

    We only support files under the configured curriculum bronze root, because
    the delete cascade needs to know the `week`, `folder`, and `filename` to
    remove corresponding rows from the silver/vector tables.

    Returns:
        (catalog, schema, volume, week, file_name)

    Notes:
      * `folder` itself isn't returned because the downstream tables store the
        semantic `content_type` derived from that segment, not the raw folder
        name. The mapping is handled by _volume_folder_to_content_type().
      * Raises HTTP 400 (not 500) for malformed user input — this is a client
        error, not a server fault.
    """
    parts = [p for p in volume_path.split("/") if p]
    # Expect: Volumes cat sch vol week folder file
    if len(parts) < 7 or parts[0] != "Volumes":
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid curriculum volume path. Expected "
                "/Volumes/<catalog>/<schema>/<volume>/<week>/<folder>/<file>."
            ),
        )

    catalog, schema, volume = parts[1], parts[2], parts[3]
    week = parts[4]
    file_name = parts[-1]
    return catalog, schema, volume, week, file_name


def _volume_folder_to_content_type(volume_path: str) -> str:
    """
    Convert the curriculum bronze folder segment to the content_type used in SQL.

    Bronze layout:
        .../<week>/markdown/<file>.md   -> silver/vector content_type = 'lesson_markdown'
        .../<week>/pdfs/<file>.pdf      -> silver/vector content_type = 'pdf'
        .../<week>/quizzes/<file>.json  -> silver/vector content_type = 'quiz'

    This mapping is part of the data contract with the silver chunker notebook.
    Keeping it centralized avoids duplicating string literals across multiple SQL
    statements and makes future folder renames explicit.
    """
    parts = [p for p in volume_path.split("/") if p]
    folder = parts[5] if len(parts) >= 7 else ""
    mapping = {
        "markdown": "lesson_markdown",
        "pdfs": "pdf",
        "quizzes": "quiz",
    }
    content_type = mapping.get(folder)
    if content_type is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported curriculum folder '{folder}'. "
                "Expected one of: markdown, pdfs, quizzes."
            ),
        )
    return content_type


def _delete_bronze_file(volume_path: str) -> None:
    """Delete the original file from the bronze Unity Catalog volume."""
    client = _client()
    try:
        client.files.delete(volume_path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete bronze file '{volume_path}': {exc}",
        ) from exc


def _delete_from_table(table_name: str, week: str, file_name: str, *, json_metadata: bool = False) -> int:
    """
    Delete rows for one source file from a Delta table and return rows affected.

    We first COUNT(*) to drive an accurate success toast in the UI and to make
    the operation idempotent-ish: if zero rows match, we skip the DELETE rather
    than issuing a no-op write. This is helpful when bronze existed but the ETL
    hadn't processed the file yet.

    Matching strategy — (week, source_file):
      A (week, source_file) pair uniquely identifies one file's chunks. The
      three bronze folders take different extensions (markdown=.md, pdfs=.pdf,
      quizzes=.json), so the same basename can never collide across content
      types within a week. We match source_file by EXACT basename because both
      tables store the bare filename (e.g. "intro_to_strings.md"), not a path —
      the old `LIKE '%/<file>'` pattern required a slash and so matched nothing.

      We deliberately do NOT filter on content_type. Silver stores the raw
      values 'markdown'/'pdf'/'quiz', which never matched the admin folder
      mapping ('lesson_markdown'/...), so an earlier version of this predicate
      silently matched zero rows on silver and left chunks orphaned.

    Schema difference between the two cascade targets — the `json_metadata` flag:
      * SILVER_TABLE stores week/source_file as top-level columns.
      * VECTOR_TABLE (capstone_vector_store) stores them INSIDE a JSON string
        `metadata` column — its real columns are (id, text, metadata,
        created_at). So week/source_file are reached via the `metadata:field`
        semi-structured accessor, not as bare columns. This is exactly why the
        old code failed with UNRESOLVED_COLUMN `week` against the vector table:
        it assumed flat columns that have never existed there.

    Escaping: file_name and week are escaped via _sql_escape before interpolation.
    """
    safe_file = _sql_escape(file_name)
    safe_week = _sql_escape(week)

    # Pick the column accessors for this table's shape: bare columns for the
    # silver table, JSON-path accessors for the vector store's metadata blob.
    week_col = "metadata:week" if json_metadata else "week"
    file_col = "metadata:source_file" if json_metadata else "source_file"
    where = f"{week_col} = '{safe_week}' AND {file_col} = '{safe_file}'"

    count_rows = _run_sql(f"SELECT COUNT(*) AS n FROM {table_name} WHERE {where}")
    rows_to_delete = int(count_rows[0][0] or 0) if count_rows else 0

    if rows_to_delete == 0:
        return 0

    _execute(f"DELETE FROM {table_name} WHERE {where}")
    return rows_to_delete


def _sync_vector_index() -> None:
    """
    Trigger a Delta Sync on the Vector Search index after deleting source rows.

    The index is configured as TRIGGERED, so deletes in VECTOR_TABLE are not
    reflected until we explicitly sync. This call is best-effort from the API
    perspective: if it fails, we surface a 500 because the UI promise is that a
    delete removes the file from semantic search as well, not just from bronze.
    """
    try:
        _vector_client().get_index(index_name=VECTOR_INDEX).sync()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Vector index sync failed for '{VECTOR_INDEX}': {exc}",
        ) from exc


@router.delete("/curriculum/file")
def delete_curriculum_file(req: DeleteFileRequest):
    """
    Delete a curriculum file across the full retrieval stack.

    Steps:
      1. Delete the original bronze file from the UC volume.
      2. Delete corresponding chunk rows from the silver table.
      3. Delete corresponding rows from the vector store Delta table.
      4. Trigger a sync on the Vector Search index so semantic search reflects
         the deletion.

    The operation is intentionally ordered "bronze first" because the user action
    is fundamentally a source-of-truth delete. If a downstream cleanup step
    fails, we return a 500 with a precise message so the admin knows manual
    remediation may be needed.
    """
    catalog, schema, volume, week, file_name = _parse_volume_path(req.path)
    # Called for its validation side-effect only: it raises 400 if the folder
    # segment isn't markdown/pdfs/quizzes. The returned content_type is no
    # longer used as a delete predicate — see _delete_from_table for why.
    _volume_folder_to_content_type(req.path)

    # Enforce that callers can only delete from the configured curriculum root.
    expected_prefix = f"/Volumes/{catalog}/{schema}/{volume}"
    if not req.path.startswith(expected_prefix):
        raise HTTPException(status_code=400, detail="Invalid volume path")

    _delete_bronze_file(req.path)

    try:
        silver_rows = _delete_from_table(SILVER_TABLE, week, file_name)
    except HTTPException as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Bronze deleted but silver cleanup failed for '{file_name}': "
                f"{exc.detail}"
            ),
        ) from exc

    try:
        vector_rows = _delete_from_table(VECTOR_TABLE, week, file_name, json_metadata=True)
    except HTTPException as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Bronze/silver deleted but vector-table cleanup failed for "
                f"'{file_name}': {exc.detail}"
            ),
        ) from exc

    try:
        _sync_vector_index()
    except HTTPException as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Data rows deleted for '{file_name}' but vector index sync failed: "
                f"{exc.detail}"
            ),
        ) from exc

    return {
        "deleted": True,
        "silver_rows": silver_rows,
        "vector_rows": vector_rows,
        "index_sync_triggered": True,
    }


# --- ETL run status endpoint -------------------------------------------------
# After an upload, the frontend polls this endpoint every few seconds to show
# an "ETL running / succeeded / failed" toast. The upload endpoint returns only
# the run_id because starting the job is fast; reading the eventual result state
# requires separate polling against the Jobs API.

@router.get("/curriculum/etl-run/{run_id}")
def get_etl_run(run_id: int):
    """
    Return the status of a curriculum ETL Lakeflow Job run.

    Response shape is intentionally frontend-friendly and stable — the React
    hook shouldn't need to know the Databricks SDK object model or enum names.

    Fields:
      run_id            — numeric Databricks run ID
      life_cycle_state  — e.g. PENDING / RUNNING / TERMINATED
      result_state      — e.g. SUCCESS / FAILED / TIMEDOUT / CANCELED / None
      state_message     — human-readable message from the Jobs API
      is_terminal       — convenience boolean for polling stop condition
      run_page_url      — deep link into the Databricks UI when available
    """
    client = _client()
    try:
        run = client.jobs.get_run(run_id=run_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch ETL run {run_id}: {exc}",
        ) from exc

    state = run.state
    life_cycle = str(state.life_cycle_state) if state and state.life_cycle_state else None
    result_state = str(state.result_state) if state and state.result_state else None
    message = state.state_message if state and state.state_message else None

    # Terminal means the UI can stop polling. Jobs uses TERMINATED for both
    # success and failure, and can also end as SKIPPED / INTERNAL_ERROR for some
    # failure modes depending on task setup.
    terminal_life_cycles = {"TERMINATED", "SKIPPED", "INTERNAL_ERROR"}
    is_terminal = (life_cycle or "") in terminal_life_cycles

    return {
        "run_id": run_id,
        "life_cycle_state": life_cycle,
        "result_state": result_state,
        "state_message": message,
        "is_terminal": is_terminal,
        "run_page_url": run.run_page_url,
    }


# --- Upload endpoint helpers -------------------------------------------------

def _derive_extension(file_name: str) -> str:
    """Return the lowercase file extension including the leading dot."""
    _, dot, ext = file_name.rpartition(".")
    return f".{ext.lower()}" if dot else ""


def _validate_upload_target(folder_name: str, upload_file_name: str) -> None:
    """
    Enforce that uploaded files match the allowed extensions for the folder.

    This catches mistakes early in the admin UI and keeps the bronze layout
    consistent with downstream assumptions in the chunker / parser jobs.
    """
    allowed = FOLDER_ALLOWED_EXTENSIONS.get(folder_name)
    if allowed is None:
        raise HTTPException(status_code=400, detail=f"Unsupported folder: {folder_name}")

    ext = _derive_extension(upload_file_name)
    if ext not in allowed:
        allowed_str = ", ".join(sorted(allowed))
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid file type for folder '{folder_name}'. "
                f"Allowed: {allowed_str}. Got: {ext or 'no extension'}"
            ),
        )


def _workspace_host() -> str:
    """
    Return a normalized workspace host without a trailing slash.

    Used only for constructing deep links back to Databricks Jobs UI. We strip
    the trailing slash so concatenations like f"{host}/jobs/..." don't produce
    a double slash.
    """
    return os.environ["DATABRICKS_HOST"].rstrip("/")


def _start_etl_run_for_upload(week_name: str, folder_name: str, volume_path: str) -> tuple[int | None, str | None]:
    """
    Kick off the curriculum ETL job after a successful bronze upload.

    Returns:
      (run_id, run_page_url) on success
      (None, None) if the job couldn't be started for a known/handled reason

    Why best-effort instead of hard-failing the upload?
      The file is already durably written to bronze at this point. Even if the
      ETL trigger fails, the scheduled / file-arrival job path can still pick it
      up later, so it's better UX to report a successful upload and let the UI
      show "ETL not started" than to tell the user the whole action failed.

    Parameters are passed to the job to make the notebook/task future-proof even
    though the current job may not yet consume them all. They also appear in the
    run details UI, which is useful when debugging uploads.
    """
    client = _client()
    try:
        job_id = _get_etl_job_id()
        run = client.jobs.run_now(
            job_id=job_id,
            job_parameters={
                "week_name": week_name,
                "folder_name": folder_name,
                "volume_path": volume_path,
            },
        )
    except HTTPException:
        # _get_etl_job_id() may raise a structured HTTPException — preserve it
        # for the caller to log/handle as a best-effort failure.
        raise
    except Exception as exc:  # noqa: BLE001
        # Reset the cached job id if the run_now call itself fails — the most
        # common reason is that the bundle was re-deployed and the old job ID is
        # stale. Next upload will force a re-discovery.
        global _etl_job_id
        _etl_job_id = None
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start curriculum ETL job: {exc}",
        ) from exc

    run_id = getattr(run, "run_id", None)
    if run_id is None:
        return None, None

    return run_id, f"{_workspace_host()}/jobs/{job_id}/runs/{run_id}"


@router.post("/curriculum/weeks/{week_name}/{folder_name}/upload")
def upload_file_to_folder(week_name: str, folder_name: str, file: UploadFile = File(...)):
    client = _client()
    target_dir = f"{_week_path(week_name)}/{folder_name}"
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    _validate_upload_target(folder_name, file.filename)
    target_path = f"{target_dir}/{file.filename}"

    try:
        data = file.file.read()
        client.files.upload(
            target_path,
            io.BytesIO(data),
            overwrite=True,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc
    finally:
        try:
            file.file.close()
        except Exception:
            pass

    etl_run_id: int | None = None
    etl_run_url: str | None = None
    try:
        etl_run_id, etl_run_url = _start_etl_run_for_upload(
            week_name=week_name,
            folder_name=folder_name,
            volume_path=target_path,
        )
    except HTTPException as exc:
        # Best-effort only — keep the upload successful, but log the failure so
        # operators can diagnose why the ETL trigger didn't fire.
        logger.warning(
            "Upload succeeded but ETL trigger failed for %s: %s",
            target_path,
            exc.detail,
        )

    return {
        "uploaded": True,
        "path": target_path,
        "etl_run_id": etl_run_id,
        "etl_run_url": etl_run_url,
    }


# ── Audit Log ────────────────────────────────────────────────────────────────

@router.get("/audit")
def get_audit_log(page: int = 1, limit: int = 50, intent: str | None = None):
    offset = (page - 1) * limit
    where = f"WHERE intent = '{intent}'" if intent else ""
    count_sql = f"SELECT COUNT(*) FROM interaction_logs {where}"
    data_sql = f"""
      SELECT timestamp, session_id, user_input, intent, attempt
      FROM interaction_logs
      {where}
      ORDER BY timestamp DESC
      LIMIT {limit} OFFSET {offset}
    """
    total_rows = _run_sql(count_sql)
    data_rows = _run_sql(data_sql)

    total = int(total_rows[0][0]) if total_rows else 0
    entries = [
        {
            "timestamp": r[0],
            "session_id": r[1],
            "user_input": r[2],
            "intent": r[3],
            "attempt": r[4],
        }
        for r in data_rows
    ]
    return {
        "entries": entries,
        "total": total,
        "page": page,
        "limit": limit,
    }
