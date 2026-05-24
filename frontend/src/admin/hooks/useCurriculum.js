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

  const deleteFile = useCallback(async (path) => {
    setError(null);
    try {
      await apiDelete(path);
      setFiles((prev) => prev.filter((f) => f.path !== path));
    } catch (e) {
      setError(e.message);
    }
  }, []);

  return {
    view,
    weeks,
    selectedWeek,
    selectedFolder,
    files,
    loading,
    error,
    loadWeeks,
    selectWeek,
    selectFolder,
    back,
    createWeek,
    uploadFile,
    deleteFile,
  };
}
