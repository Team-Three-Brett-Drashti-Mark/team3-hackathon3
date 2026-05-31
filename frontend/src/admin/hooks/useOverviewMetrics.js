import { useState, useEffect } from "react";
import { fetchOverview } from "../services/adminApi";

const OVERVIEW_TIMEOUT_MS = 15000;

// Fetches and caches overview metrics from the backend.
// Re-fetches when `refreshKey` changes (pass Date.now() to force a reload).
export function useOverviewMetrics(refreshKey = 0) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), OVERVIEW_TIMEOUT_MS);

    setLoading(true);
    setError(null);

    fetchOverview({ signal: controller.signal })
      .then(setData)
      .catch((e) => {
        if (e.name === "AbortError") {
          setError("Overview request timed out after 15 seconds. Try Refresh.");
          return;
        }
        setError(e.message);
      })
      .finally(() => {
        clearTimeout(timer);
        setLoading(false);
      });

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [refreshKey]);

  return { data, loading, error };
}
