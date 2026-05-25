import React, { useEffect, useState } from "react";
import { colors, labelStyle } from "../../../student/styles/theme";
import { useCurriculum } from "../../hooks/useCurriculum";
import WeekList from "./WeekList";
import FolderView from "./FolderView";
import FileDropZone from "./FileDropZone";
import FileList from "./FileList";
import NewWeekModal from "./NewWeekModal";

// Breadcrumb-driven curriculum browser: weeks → folders → files.
// State machine (view: 'weeks' | 'folders' | 'files') lives in useCurriculum.
export default function CurriculumPage() {
  const curriculum = useCurriculum();
  const [showNewWeek, setShowNewWeek] = useState(false);
  const [uploading, setUploading] = useState(false);

  // Load weeks on mount.
  useEffect(() => {
    curriculum.loadWeeks();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-dismiss the SUCCESS toast 4s after a delete completes. We
  // intentionally do not auto-dismiss the error toast: if the cascade fails
  // partway (e.g. "Bronze deleted but silver cleanup failed"), the admin
  // needs time to actually read the message and decide whether to reconcile
  // manually. Forcing them to chase a fading toast would be hostile.
  //
  // Cleanup on unmount / phase change cancels the timer so we never call
  // clearDeleteStatus against a stale phase (which would no-op anyway, but
  // saves a render).
  useEffect(() => {
    if (curriculum.deleteStatus.phase !== "done") return;
    const t = setTimeout(() => curriculum.clearDeleteStatus(), 4000);
    return () => clearTimeout(t);
  // clearDeleteStatus is a stable useCallback in the hook; depending on
  // phase alone keeps this effect from re-firing on unrelated re-renders.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [curriculum.deleteStatus.phase]);

  const handleUpload = async (file) => {
    setUploading(true);
    try {
      await curriculum.uploadFile(file);
    } finally {
      setUploading(false);
    }
  };

  const handleCreateWeek = async (name) => {
    await curriculum.createWeek(name);
    setShowNewWeek(false);
  };

  // Wraps the hook's deleteFile with a confirmation prompt.
  //
  // We use the native window.confirm() rather than a styled modal because:
  //   - It's blocking by default — the user can't accidentally click anything
  //     else on the page until they answer.
  //   - It can't be missed visually (unlike a corner toast or inline banner).
  //   - The cascade is destructive across four data layers — making the
  //     friction VERY explicit is intentional, not a UX wart.
  //
  // Once confirmed, control returns to deleteFile() in the hook which handles
  // the phase transitions; this function deliberately doesn't await it so the
  // click handler returns immediately and the toast can render.
  const handleDelete = (path) => {
    const filename = path.split("/").pop();
    const ok = window.confirm(
      `Remove ${filename}?\n\nThis deletes the file and all related chunks from the curriculum, vector store, and search index.`
    );
    if (!ok) return;
    curriculum.deleteFile(path);
  };

  // Build breadcrumb segments from current drill-down level.
  const breadcrumbs = [
    { label: "Curriculum", onClick: () => { curriculum.back(); curriculum.back(); } },
    ...(curriculum.selectedWeek
      ? [{ label: curriculum.selectedWeek, onClick: curriculum.view === "files" ? curriculum.back : null }]
      : []),
    ...(curriculum.selectedFolder ? [{ label: `${curriculum.selectedFolder}/` }] : []),
  ];

  return (
    <div style={{ padding: "28px 32px", maxWidth: 820 }}>
      {/* Header + breadcrumb */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, marginBottom: 8 }}>
          {breadcrumbs.map((crumb, i) => (
            <React.Fragment key={i}>
              {i > 0 && <span style={{ color: colors.border }}>/</span>}
              {crumb.onClick ? (
                <button
                  onClick={crumb.onClick}
                  style={{
                    background: "none", border: "none", padding: 0,
                    color: colors.muted, cursor: "pointer", fontSize: 13,
                    textDecoration: "underline",
                  }}
                >
                  {crumb.label}
                </button>
              ) : (
                <span style={{ color: colors.text, fontWeight: 600 }}>{crumb.label}</span>
              )}
            </React.Fragment>
          ))}
        </div>

        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: colors.text }}>
          {curriculum.view === "weeks" && "Curriculum library"}
          {curriculum.view === "folders" && curriculum.selectedWeek}
          {curriculum.view === "files" && `${curriculum.selectedWeek} / ${curriculum.selectedFolder}/`}
        </h1>
      </div>

      {curriculum.error && (
        <div style={{
          background: colors.errorBg, color: colors.errorFg,
          border: `1px solid ${colors.errorFg}`,
          borderRadius: 6, padding: "10px 14px", marginBottom: 16, fontSize: 13,
        }}>
          {curriculum.error}
        </div>
      )}

      {/*
        Cascade-delete status toast.
        Visible whenever the hook's deleteStatus.phase is non-idle. Three states:
          - "deleting": spinner + message, no dismiss button (in-flight requests
            can't be cancelled, and a dismiss button would imply otherwise).
          - "done":     plain styling, dismiss button shown. Auto-dismisses
            after 4s via the useEffect above.
          - "error":    red styling (errorBg/errorFg), dismiss button shown,
            stays up until the user closes it.
        The spinner CSS keyframe is injected via a <style> child rather than a
        global stylesheet so the toast is self-contained — no orphaned
        animations if this component ever gets ripped out.
      */}
      {curriculum.deleteStatus.phase !== "idle" && (
        <div style={{
          background: curriculum.deleteStatus.phase === "error" ? colors.errorBg : colors.surface,
          color: curriculum.deleteStatus.phase === "error" ? colors.errorFg : colors.text,
          border: `1px solid ${curriculum.deleteStatus.phase === "error" ? colors.errorFg : colors.border}`,
          borderRadius: 6,
          padding: "10px 14px",
          marginBottom: 16,
          fontSize: 13,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {/* Spinner: only renders during the in-flight phase. Built from a
                bordered circle with a single contrast-colored top edge that
                rotates — small enough (12px) to sit inline with body text. */}
            {curriculum.deleteStatus.phase === "deleting" && (
              <span style={{
                display: "inline-block",
                width: 12, height: 12,
                border: `2px solid ${colors.border}`,
                borderTopColor: colors.accent,
                borderRadius: "50%",
                animation: "pathwise-spin 0.8s linear infinite",
              }} />
            )}
            <span>{curriculum.deleteStatus.message}</span>
          </div>
          {/* Dismiss button: hidden while deleting (can't cancel an in-flight
              cascade), shown for done + error so the user can clear the toast
              on their own schedule. */}
          {curriculum.deleteStatus.phase !== "deleting" && (
            <button
              onClick={curriculum.clearDeleteStatus}
              style={{
                background: "transparent", border: "none", padding: "0 4px",
                cursor: "pointer", fontSize: 14, lineHeight: 1, color: "inherit",
              }}
              aria-label="Dismiss"
            >
              ✕
            </button>
          )}
          {/* Scoped keyframe definition — see component-header comment. */}
          <style>{`@keyframes pathwise-spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      )}

      {/* Week list */}
      {curriculum.view === "weeks" && (
        <WeekList
          weeks={curriculum.weeks}
          loading={curriculum.loading}
          onSelect={curriculum.selectWeek}
          onNewWeek={() => setShowNewWeek(true)}
        />
      )}

      {/* Folder cards */}
      {curriculum.view === "folders" && (
        <FolderView
          weekName={curriculum.selectedWeek}
          onSelect={curriculum.selectFolder}
        />
      )}

      {/* File list + drop zone */}
      {curriculum.view === "files" && (
        <>
          <FileDropZone onUpload={handleUpload} uploading={uploading} />
          <FileList
            files={curriculum.files}
            loading={curriculum.loading}
            onDelete={handleDelete}
            disabledPath={curriculum.deleteStatus.path}
          />
        </>
      )}

      {showNewWeek && (
        <NewWeekModal
          onConfirm={handleCreateWeek}
          onCancel={() => setShowNewWeek(false)}
        />
      )}
    </div>
  );
}
