import { useState, useEffect } from "react";
import { fetchOverview } from "../services/adminApi";

// Overview metrics come from a serverless SQL warehouse: ~0.3s warm, but a cold
// start (after the warehouse's 10-min auto-stop) can take 10s+. TWO separate
// things were surfacing to the user as "Overview request timed out":
//
//   1. A non-timeout abort mislabeled as a timeout. Navigating between admin
//      pages unmounts this page, and the effect cleanup calls controller.abort().
//      React StrictMode also mounts→unmounts→remounts on every mount. The old
//      code treated EVERY AbortError as a timeout, so a fast request that got
//      aborted by navigation/cleanup painted a timeout banner. That's why a hard
//      refresh (one clean mount) worked but leaving and returning re-broke it.
//
//   2. A genuinely slow cold start exceeding the old 15s budget.
//
// Fix: ONLY the timeout timer is allowed to raise a timeout error (didTimeout).
// An abort from cleanup/unmount is ignored via the `active` guard. Cold starts
// get a 45s budget and one retry, since the first request is what wakes the
// warehouse and the retry should land warm.
const OVERVIEW_TIMEOUT_MS = 45000;
const MAX_ATTEMPTS = 2;

// Fetches and caches overview metrics from the backend.
// Re-fetches when `refreshKey` changes (pass Date.now() to force a reload).
export function useOverviewMetrics(refreshKey = 0) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    let currentController = null;

    async function load() {
      setLoading(true);
      setError(null);

      for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
        const controller = new AbortController();
        currentController = controller;
        // didTimeout marks an abort as a REAL timeout (the timer fired), so we
        // can distinguish it from a cleanup/unmount abort that must stay silent.
        let didTimeout = false;
        const timer = setTimeout(() => {
          didTimeout = true;
          controller.abort();
        }, OVERVIEW_TIMEOUT_MS);

        try {
          const result = await fetchOverview({ signal: controller.signal });
          clearTimeout(timer);
          if (active) {
            setData(result);
            setError(null);
            setLoading(false);
          }
          return;
        } catch (e) {
          clearTimeout(timer);

          // Effect was torn down (navigated away / refreshKey changed). The
          // abort came from cleanup, not a timeout — drop it silently so we
          // never paint a stale error on a page that's unmounting or refetching.
          if (!active) return;

          const realTimeout = didTimeout && e.name === "AbortError";
          // Retry once on a real timeout: attempt 1 likely just woke the
          // warehouse, so attempt 2 should hit it warm.
          if (realTimeout && attempt < MAX_ATTEMPTS) continue;

          setError(
            realTimeout
              ? "Overview request timed out — the metrics warehouse may be waking up. Hit Refresh in a moment."
              // A non-timeout AbortError that slipped past the active guard is
              // still navigation noise, not a real failure — surface nothing.
              : e.name === "AbortError" ? null : e.message
          );
          setLoading(false);
          return;
        }
      }
    }

    load();

    return () => {
      active = false;
      if (currentController) currentController.abort();
    };
  }, [refreshKey]);

  return { data, loading, error };
}
