import { useState, useCallback, useRef, useEffect } from "react";
import {
  fetchWeeks,
  createWeek as apiCreateWeek,
  fetchFolderFiles,
  uploadFile as apiUpload,
  deleteFile as apiDelete,
  fetchEtlRun as apiFetchEtlRun,
} from "../services/adminApi";

// How often the hook polls the backend for ETL run status. 3 seconds is a
// trade-off: low enough that the toast feels live (most ETL runs finish in
// 30-90s, so the admin sees 10-30 updates), high enough that we don't
// hammer the Databricks Jobs API. Pulled out here so a future debug build
// can tune it without searching the file.
const ETL_POLL_INTERVAL_MS = 3000;

// Manages the three-level drill-down: weeks → folders → files.
// view: 'weeks' | 'folders' | 'files'
export function useCurriculum() {
  const [view, setView] = useState("weeks");
  const [weeks, setWeeks] = useState([]);
  const [selectedWeek, setSelectedWeek] = useState(null);
  const [selectedFolder, setSelectedFolder] = useState(null);
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  // Tracks the cascade delete so the UI can show "deleting / done / error"
  // toasts and disable the in-flight row's remove button.
  //
  //   phase:   simple state machine — only ever transitions
  //              idle → deleting → (done | error) → idle
  //            We hold the state here (not page-local) so any consumer of the
  //            hook can render off it: today that's just CurriculumPage, but
  //            if a sidebar or breadcrumb wants to mirror the toast later it
  //            can read this directly without prop-drilling.
  //   path:    bronze path of the file currently being deleted. Used by
  //            FileList to know which row to dim and disable. Null while idle
  //            so the disabled-row check is a simple `disabledPath === f.path`.
  //   message: user-facing toast text. Pre-formatted here (not in the JSX) so
  //            the page component stays a dumb presenter.
  const [deleteStatus, setDeleteStatus] = useState({
    phase: "idle", // "idle" | "deleting" | "done" | "error"
    path: null,
    message: "",
  });

  // Tracks the ETL job run kicked off by the backend after a successful
  // upload (see app/admin.py:upload_file). Lifecycle:
  //
  //   idle → running → (success | failed | error) → idle
  //
  //   phase:      coarse state for the toast. "running" while the job is
  //               doing its thing; "success"/"failed" mirror the
  //               Databricks result_state on terminal; "error" means we
  //               couldn't even poll (network, 404, etc).
  //   runId:      Databricks run_id, kept so the polling effect knows
  //               which run to query.
  //   runPageUrl: deep link into the Jobs UI for the toast's "view run"
  //               affordance.
  //   message:    pre-formatted human-readable status.
  //
  // The drop zone uses `phase === "running"` to disable itself so an
  // admin can't queue a second upload while the first one's ETL is still
  // in flight — that would race two MERGEs against the silver table and
  // typically cost more time than just waiting.
  const [etlStatus, setEtlStatus] = useState({
    phase: "idle", // "idle" | "running" | "success" | "failed" | "error"
    runId: null,
    runPageUrl: null,
    message: "",
  });

  // Reference to the active poll timer so the polling effect can cancel
  // any in-flight schedule when the run terminates or the component
  // unmounts. We use a ref (not state) because mutating it should NOT
  // trigger a re-render — and the timer ID is internal plumbing, not UI.
  const etlPollTimerRef = useRef(null);

  const loadWeeks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchWeeks();
      setWeeks(res.weeks);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const selectWeek = useCallback((name) => {
    setSelectedWeek(name);
    setSelectedFolder(null);
    setView("folders");
  }, []);

  const selectFolder = useCallback(async (folder) => {
    setSelectedFolder(folder);
    setView("files");
    setLoading(true);
    setError(null);
    try {
      const res = await fetchFolderFiles(selectedWeek, folder);
      setFiles(res.files);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedWeek]);

  const back = useCallback(() => {
    if (view === "files") {
      setView("folders");
      setSelectedFolder(null);
      setFiles([]);
    } else if (view === "folders") {
      setView("weeks");
      setSelectedWeek(null);
    }
  }, [view]);

  const createWeek = useCallback(async (name) => {
    setLoading(true);
    setError(null);
    try {
      await apiCreateWeek(name);
      await loadWeeks(); // refresh list
    } catch (e) {
      setError(e.message);
      throw e; // re-throw so the modal can show inline error
    } finally {
      setLoading(false);
    }
  }, [loadWeeks]);

  // ── ETL run status polling ───────────────────────────────────────────
  //
  // Single recursive timer loop rather than setInterval: each tick
  // schedules the next only after the previous fetch resolves. This
  // avoids piling up overlapping requests if the backend hiccups and a
  // single poll takes >ETL_POLL_INTERVAL_MS, and it makes "stop when
  // terminal" a single `return` instead of clearInterval bookkeeping.
  //
  // The terminal-state mapping lives here (not in the toast component)
  // so any future consumer reading etlStatus sees a clean
  // success/failed/error phase instead of having to interpret raw
  // Databricks result_state values.
  const pollEtlRunOnce = useCallback(async (runId, runPageUrl) => {
    try {
      const r = await apiFetchEtlRun(runId);
      if (!r.is_terminal) {
        setEtlStatus({
          phase: "running",
          runId,
          runPageUrl: r.run_page_url || runPageUrl,
          message: r.state_message
            ? `ETL pipeline running — ${r.state_message}`
            : "ETL pipeline running — chunking and embedding new content…",
        });
        etlPollTimerRef.current = setTimeout(
          () => pollEtlRunOnce(runId, runPageUrl),
          ETL_POLL_INTERVAL_MS,
        );
        return;
      }
      // Terminal: translate Databricks result_state into our phase.
      // SUCCESS → success; everything else (FAILED, TIMEDOUT, CANCELED,
      // INTERNAL_ERROR) → failed. SKIPPED life-cycle without a
      // result_state is also treated as failed so the toast surfaces it.
      const succeeded = r.result_state === "SUCCESS";
      setEtlStatus({
        phase: succeeded ? "success" : "failed",
        runId,
        runPageUrl: r.run_page_url || runPageUrl,
        message: succeeded
          ? "ETL complete — new content indexed and ready to search."
          : `ETL failed${r.result_state ? ` (${r.result_state})` : ""}${
              r.state_message ? `: ${r.state_message}` : ""
            }.`,
      });
    } catch (e) {
      // Polling itself errored — usually a 404 (run deleted) or network
      // blip. Surface as "error" so the toast can show a dismissable
      // message instead of spinning forever.
      setEtlStatus({
        phase: "error",
        runId,
        runPageUrl,
        message: `Couldn't read ETL status: ${e.message}`,
      });
    }
  }, []);

  const uploadFile = useCallback(async (file) => {
    setError(null);
    try {
      const res = await apiUpload(selectedWeek, selectedFolder, file);
      // Refresh the file list after upload — the file is in bronze
      // immediately even if the ETL run is still pending.
      const refreshed = await fetchFolderFiles(selectedWeek, selectedFolder);
      setFiles(refreshed.files);

      // If the backend kicked off an ETL run, start polling for status.
      // Cancel any prior timer first so we don't end up with two loops
      // racing (e.g. quick successive uploads).
      if (res?.etl_run_id) {
        if (etlPollTimerRef.current) {
          clearTimeout(etlPollTimerRef.current);
          etlPollTimerRef.current = null;
        }
        setEtlStatus({
          phase: "running",
          runId: res.etl_run_id,
          runPageUrl: res.etl_run_url,
          message: "ETL pipeline running — chunking and embedding new content…",
        });
        // Kick off the loop immediately; subsequent ticks self-schedule.
        pollEtlRunOnce(res.etl_run_id, res.etl_run_url);
      }
    } catch (e) {
      setError(e.message);
      throw e;
    }
  }, [selectedWeek, selectedFolder, pollEtlRunOnce]);

  // Stop polling on unmount. The timer ref lives across renders, so the
  // cleanup function captured by useEffect can safely call clearTimeout
  // on whatever's pending — clearTimeout on null/undefined is a no-op.
  useEffect(() => {
    return () => {
      if (etlPollTimerRef.current) {
        clearTimeout(etlPollTimerRef.current);
      }
    };
  }, []);

  // Reset the ETL toast back to idle. Used by the page's auto-dismiss
  // effect for "success" and by the toast's ✕ button for "failed"/"error".
  // Also kills any in-flight poll timer so a manual dismiss doesn't get
  // re-overwritten by a late-arriving fetch.
  const clearEtlStatus = useCallback(() => {
    if (etlPollTimerRef.current) {
      clearTimeout(etlPollTimerRef.current);
      etlPollTimerRef.current = null;
    }
    setEtlStatus({ phase: "idle", runId: null, runPageUrl: null, message: "" });
  }, []);

  // Drives the cascade delete from the UI side.
  //
  // Flow:
  //   1. Switch into "deleting" phase immediately so the toast + spinner
  //      appear on the same click that fired the request. Holding `path`
  //      here is what causes FileList to dim/disable the row — important
  //      because the cold-warehouse case can take a full minute, plenty of
  //      time for a confused user to double-click.
  //   2. Wait for the cascade. Cold-warehouse worst case ~60s; warm ~2-3s.
  //      We do NOT show a separate "still working" message because the
  //      backend doesn't expose progress and inventing one would lie.
  //   3. On success: optimistically prune the file from the local list so
  //      the user doesn't have to wait for a refetch. silver_rows comes
  //      straight from the API and is the user-meaningful "how many chunks
  //      did this affect?" number — vector_rows can be 0 in the fallback
  //      branch (see adminApi.js / app/admin.py), which would be confusing
  //      to surface.
  //   4. On failure: keep the file in the list (the cascade may have failed
  //      mid-way, so the user can retry). The error message is whatever the
  //      backend put in `detail`, which tells the admin exactly which step
  //      broke — e.g. "Bronze deleted but silver cleanup failed: ...".
  const deleteFile = useCallback(async (path) => {
    setError(null);
    const filename = path.split("/").pop();
    setDeleteStatus({
      phase: "deleting",
      path,
      message: `Removing ${filename} from curriculum, chunks, and search index…`,
    });
    try {
      const res = await apiDelete(path);
      setFiles((prev) => prev.filter((f) => f.path !== path));
      // silver_rows is the row count from the silver Delta table; we report
      // it because vector_rows can legitimately be 0 in the metadata-fallback
      // branch even though chunks were removed. silver_rows is the more
      // user-meaningful "chunks deleted" number.
      const n = res?.silver_rows ?? 0;
      setDeleteStatus({
        phase: "done",
        path: null,
        message: `Removed ${filename} — ${n} chunk${n === 1 ? "" : "s"} deleted, search index updating.`,
      });
    } catch (e) {
      // The backend's `detail` field flows through Error.message (see
      // adminApi.deleteFile), so this preserves the WHICH-STEP-FAILED context.
      setDeleteStatus({
        phase: "error",
        path: null,
        message: `Failed to remove ${filename}: ${e.message}`,
      });
    }
  }, []);

  // Two callers:
  //   - the page's auto-dismiss timer for "done" toasts (~4s after success)
  //   - the toast's ✕ button for "error" state (errors don't auto-dismiss so
  //     the user has time to read what broke)
  // Kept as a stable callback so consumers can put it in useEffect dep arrays
  // without retriggering on every render.
  const clearDeleteStatus = useCallback(() => {
    setDeleteStatus({ phase: "idle", path: null, message: "" });
  }, []);

  return {
    view,
    weeks,
    selectedWeek,
    selectedFolder,
    files,
    loading,
    error,
    deleteStatus,
    etlStatus,
    loadWeeks,
    selectWeek,
    selectFolder,
    back,
    createWeek,
    uploadFile,
    deleteFile,
    clearDeleteStatus,
    clearEtlStatus,
  };
}
