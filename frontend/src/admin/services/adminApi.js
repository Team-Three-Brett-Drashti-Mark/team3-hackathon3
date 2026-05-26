// All /admin/* API calls. Plain async functions — no React.
// Callers are responsible for error handling.

const base = () => (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export async function fetchOverview() {
  const res = await fetch(`${base()}/admin/metrics/overview`);
  if (!res.ok) throw new Error(`Overview fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchWeeks() {
  const res = await fetch(`${base()}/admin/curriculum/weeks`);
  if (!res.ok) throw new Error(`Weeks fetch failed: ${res.status}`);
  return res.json(); // { weeks: [{name, path}] }
}

export async function createWeek(weekName) {
  const res = await fetch(`${base()}/admin/curriculum/weeks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ week_name: weekName }),
  });
  if (!res.ok) throw new Error(`Create week failed: ${res.status}`);
  return res.json();
}

export async function fetchFolderFiles(week, folder) {
  const res = await fetch(`${base()}/admin/curriculum/weeks/${week}/${folder}`);
  if (!res.ok) throw new Error(`Folder fetch failed: ${res.status}`);
  return res.json(); // { files: [{name, path, size_bytes, last_modified}] }
}

// Uploads a file to bronze and (server-side) fires the curriculum ETL job
// via jobs.run_now() so the admin gets near-instant feedback instead of
// waiting for the 5-minute file_arrival safety-net trigger.
//
// The response now carries two extra fields:
//   etl_run_id:  number | null  — the Databricks Jobs run_id, used by the
//                                 useCurriculum hook to poll the status
//                                 endpoint below until the run terminates.
//   etl_run_url: string | null  — deep link into the Databricks Jobs UI for
//                                 the toast's "view run" affordance.
//
// Either field is null if the backend couldn't start the run (e.g. the
// bundle hasn't been deployed yet). In that case the upload still succeeded
// and the file_arrival trigger will catch it eventually — the UI just
// suppresses the ETL toast.
export async function uploadFile(week, folder, file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${base()}/admin/curriculum/weeks/${week}/${folder}/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    // Surface the backend's `detail` (e.g. extension validation message)
    // through Error.message so the UI can show why the upload was rejected.
    let detail = `Upload failed: ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // Response wasn't JSON — keep the status-code message.
    }
    throw new Error(detail);
  }
  // { uploaded, path, etl_run_id, etl_run_url }
  return res.json();
}

// Polls the backend for the state of a single ETL job run. Called every
// few seconds by useCurriculum until is_terminal === true.
//
// Returns the shape documented in app/admin.py:get_etl_run:
//   { run_id, life_cycle_state, result_state, state_message, is_terminal, run_page_url }
//
// Throws on 404 (run not found — stop polling) or other HTTP errors. The
// caller is expected to catch and surface the failure in the toast.
export async function fetchEtlRun(runId) {
  const res = await fetch(`${base()}/admin/curriculum/etl-run/${runId}`);
  if (!res.ok) {
    let detail = `ETL run fetch failed: ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // Non-JSON response — keep the status-code message.
    }
    throw new Error(detail);
  }
  return res.json();
}

// Triggers the cascade delete: bronze volume → silver chunks → vector store →
// semantic index sync. The backend can take 30-60s on a cold SQL warehouse
// (see app/admin.py:_poll), so callers should show an in-flight indicator
// rather than assuming this resolves quickly.
//
// On failure, the backend returns a FastAPI {detail: "..."} payload describing
// WHICH step failed (e.g. "Bronze deleted but silver cleanup failed: ..."),
// which is much more actionable than a bare status code. We propagate that
// detail string through Error.message so the UI can render it verbatim.
export async function deleteFile(path) {
  const res = await fetch(`${base()}/admin/curriculum/file`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  if (!res.ok) {
    // Default to the status-code message so we always throw something useful,
    // then upgrade to the server's `detail` field if present.
    let detail = `Delete failed: ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // Response wasn't JSON (e.g. an upstream proxy 502 page) — fall back to
      // the status-code message we already set.
    }
    throw new Error(detail);
  }
  // Response shape: { deleted, silver_rows, vector_rows, index_sync_triggered }
  // The hook uses silver_rows to render "N chunks deleted" in the success toast.
  return res.json();
}

export async function fetchAuditLog({ page = 1, limit = 50, intent = "" } = {}) {
  const params = new URLSearchParams({ page, limit, ...(intent && { intent }) });
  const res = await fetch(`${base()}/admin/audit?${params}`);
  if (!res.ok) throw new Error(`Audit log fetch failed: ${res.status}`);
  return res.json(); // { entries: [...], total, page, limit }
}
