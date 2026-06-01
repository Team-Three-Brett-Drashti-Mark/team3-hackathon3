"""
test_audit_perf.py — Smoke test for /admin/audit after the cold-start fix.

Spins up the FastAPI app in-process via TestClient, hits /admin/audit a few
times against the real Databricks workspace, and prints wall-clock timings
plus a correctness check on the response shape.

Run from the project root with the venv active and .env populated:
    python scripts/test_audit_perf.py
"""
import sys
import time
from pathlib import Path

# Make the project root importable so `from app.api import app` works when this
# script is run from anywhere.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

# Importing app.api triggers .env loading via app.main, which the admin client
# needs for DATABRICKS_HOST / DATABRICKS_TOKEN.
from app.api import app  # noqa: E402

# Also reach into admin to clear the in-process cache between scenarios so we
# can measure real round-trip times, not cache hits.
from app import admin  # noqa: E402

client = TestClient(app)


def timed_get(path: str, label: str) -> dict:
    """GET path, print elapsed wall-clock, return parsed JSON."""
    start = time.perf_counter()
    resp = client.get(path)
    elapsed = time.perf_counter() - start
    assert resp.status_code == 200, f"{label}: {resp.status_code} {resp.text}"
    data = resp.json()
    print(f"  {label:45s}  {elapsed*1000:7.1f} ms   "
          f"entries={len(data.get('entries', []))}  total={data.get('total')}")
    return data


def main():
    print("\n── /admin/audit timing ────────────────────────────────────────────────")

    # Scenario 1: cold cache, no filter — should be ONE round-trip now.
    admin._audit_cache.clear()
    d1 = timed_get("/admin/audit?page=1&limit=50", "cold (no filter)")
    assert d1["entries"], "expected non-empty entries on page 1"
    assert d1["total"] >= len(d1["entries"]), "total should be >= entries returned"
    assert d1["page"] == 1
    assert d1["limit"] == 50

    # Scenario 2: warm cache — same key, should be ~ms.
    d2 = timed_get("/admin/audit?page=1&limit=50", "warm (same key, cache hit)")
    assert d2 == d1, "cache hit should return identical payload"

    # Scenario 3: cold cache, with intent filter.
    admin._audit_cache.clear()
    d3 = timed_get(
        "/admin/audit?page=1&limit=50&intent=answer_seeking",
        "cold (intent=answer_seeking)",
    )
    # All entries on this page must match the filter.
    assert all(e["intent"] == "answer_seeking" for e in d3["entries"]), \
        "intent filter leaked non-matching rows"
    # Total should match what we know from the table stats (33 today).
    assert d3["total"] == 33, f"expected total=33 for answer_seeking, got {d3['total']}"

    # Scenario 4: page past the end — exercises the COUNT(*) fallback.
    admin._audit_cache.clear()
    d4 = timed_get(
        "/admin/audit?page=99&limit=50&intent=answer_seeking",
        "cold (page past end, fallback)",
    )
    assert d4["entries"] == [], "expected empty entries past end"
    assert d4["total"] == 33, f"fallback should still report total=33, got {d4['total']}"

    # Scenario 5: warm cache after fallback — should hit cache.
    d5 = timed_get(
        "/admin/audit?page=99&limit=50&intent=answer_seeking",
        "warm (page past end, cache hit)",
    )
    assert d5 == d4

    print("\n✓ all assertions passed\n")


if __name__ == "__main__":
    main()
