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
            onDelete={curriculum.deleteFile}
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
