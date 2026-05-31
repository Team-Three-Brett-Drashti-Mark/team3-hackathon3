// All /admin/* API calls. Plain async functions — no React.
// Callers are responsible for error handling.

const base = () => (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

async function readErrorDetail(res, fallback) {
  try {
    const body = await res.json();
    if (body?.detail) return `${fallback}: ${body.detail}`;
  } catch {
    // Response wasn't JSON — keep the fallback.
  }
  return fallback;
}

export async function fetchOverview(options = {}) {
  const res = await fetch(`${base()}/admin/metrics/overview`, options);
  if (!res.ok) throw new Error(await readErrorDetail(res, `Overview fetch failed: ${res.status}`));
  return res.json();
}

export async function fetchWeeks() {
  const res = await fetch(`${base()}/admin/curriculum/weeks`);
  if (!res.ok) throw new Error(await readErrorDetail(res, `Weeks fetch failed: ${res.status}`));
  return res.json(); // { weeks: [{name, path}] }
}

export async function createWeek(weekName) {
  const res = await fetch(`${base()}/admin/curriculum/weeks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ week_name: weekName }),
  });
  if (!res.ok) throw new Error(await readErrorDetail(res, `Create week failed: ${res.status}`));
  return res.json();
}

export async function fetchFolderFiles(week, folder) {
  const res = await fetch(`${base()}/admin/curriculum/weeks/${week}/${folder}`);
  if (!res.ok) throw new Error(await readErrorDetail(res, `Folder fetch failed: ${res.status}`));
  return res.json(); // { files: [{name, path, size_bytes, last_modified}] }
}

export async function uploadFile(week, folder, file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${base()}/admin/curriculum/weeks/${week}/${folder}/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, `Upload failed: ${res.status}`));
  }
  return res.json();
}

export async function fetchEtlRun(runId) {
  const res = await fetch(`${base()}/admin/curriculum/etl-run/${runId}`);
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, `ETL run fetch failed: ${res.status}`));
  }
  return res.json();
}

export async function deleteFile(path) {
  const res = await fetch(`${base()}/admin/curriculum/file`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, `Delete failed: ${res.status}`));
  }
  return res.json();
}

export async function fetchAuditLog({ page = 1, limit = 50, intent = "" } = {}) {
  const params = new URLSearchParams({ page, limit, ...(intent && { intent }) });
  const res = await fetch(`${base()}/admin/audit?${params}`);
  if (!res.ok) throw new Error(await readErrorDetail(res, `Audit log fetch failed: ${res.status}`));
  return res.json(); // { entries: [...], total, page, limit }
}
