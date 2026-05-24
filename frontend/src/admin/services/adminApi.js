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

export async function uploadFile(week, folder, file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${base()}/admin/curriculum/weeks/${week}/${folder}/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
}

export async function deleteFile(path) {
  const res = await fetch(`${base()}/admin/curriculum/file`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
  return res.json();
}

export async function fetchAuditLog({ page = 1, limit = 50, intent = "" } = {}) {
  const params = new URLSearchParams({ page, limit, ...(intent && { intent }) });
  const res = await fetch(`${base()}/admin/audit?${params}`);
  if (!res.ok) throw new Error(`Audit log fetch failed: ${res.status}`);
  return res.json(); // { entries: [...], total, page, limit }
}
