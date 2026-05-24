import { useState, useEffect } from "react";
import { fetchOverview } from "../services/adminApi";

// Fetches and caches overview metrics from the backend.
// Re-fetches when `refreshKey` changes (pass Date.now() to force a reload).
export function useOverviewMetrics(refreshKey = 0) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchOverview()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [refreshKey]);

  return { data, loading, error };
}
