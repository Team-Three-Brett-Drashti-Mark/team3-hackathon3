import { useState, useEffect, useCallback } from "react";
import { fetchAuditLog } from "../services/adminApi";

// Manages paginated, filterable access to the audit log.
export function useAuditLog() {
  const [entries, setEntries] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [intentFilter, setIntentFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const LIMIT = 50;

  const load = useCallback(async (p, intent) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchAuditLog({ page: p, limit: LIMIT, intent });
      setEntries(res.entries);
      setTotal(res.total);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Reload when page or filter changes.
  useEffect(() => {
    load(page, intentFilter);
  }, [page, intentFilter, load]);

  const changeIntent = useCallback((intent) => {
    setIntentFilter(intent);
    setPage(1); // reset to first page on filter change
  }, []);

  const totalPages = Math.max(1, Math.ceil(total / LIMIT));

  return {
    entries, total, page, totalPages, intentFilter,
    loading, error,
    setPage, changeIntent,
  };
}
