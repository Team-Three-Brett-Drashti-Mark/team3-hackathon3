import { useState, useCallback } from "react";
import {
  fetchWeeks,
  createWeek as apiCreateWeek,
  fetchFolderFiles,
  uploadFile as apiUpload,
  deleteFile as apiDelete,
} from "../services/adminApi";

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

  const uploadFile = useCallback(async (file) => {
    setError(null);
    try {
      await apiUpload(selectedWeek, selectedFolder, file);
      // Refresh the file list after upload
      const res = await fetchFolderFiles(selectedWeek, selectedFolder);
      setFiles(res.files);
    } catch (e) {
      setError(e.message);
      throw e;
    }
  }, [selectedWeek, selectedFolder]);

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
    loadWeeks,
    selectWeek,
    selectFolder,
    back,
    createWeek,
    uploadFile,
    deleteFile,
    clearDeleteStatus,
  };
}
