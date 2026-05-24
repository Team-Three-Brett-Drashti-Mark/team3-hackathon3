import React, { useState, useRef } from "react";
import { colors } from "../../../student/styles/theme";

// Drag-and-drop + click-to-browse upload area.
// Calls onUpload(File) for each dropped/selected file sequentially.
export default function FileDropZone({ onUpload, uploading }) {
  const [dragging, setDragging] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const inputRef = useRef(null);

  const handleFiles = async (files) => {
    setUploadError(null);
    for (const file of Array.from(files)) {
      try {
        await onUpload(file);
      } catch (e) {
        setUploadError(e.message);
        break;
      }
    }
  };

  return (
    <div style={{ marginBottom: 16 }}>
      <div
        onDragEnter={(e) => { e.preventDefault(); setDragging(true); }}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          if (!uploading) handleFiles(e.dataTransfer.files);
        }}
        onClick={() => !uploading && inputRef.current?.click()}
        style={{
          border: `2px dashed ${dragging ? colors.accent : colors.border}`,
          borderRadius: 8,
          padding: "28px 24px",
          textAlign: "center",
          cursor: uploading ? "not-allowed" : "pointer",
          background: dragging ? `${colors.accent}11` : colors.surface,
          transition: "border-color 0.15s, background 0.15s",
        }}
      >
        {uploading ? (
          <p style={{ margin: 0, fontSize: 13, color: colors.muted }}>Uploading…</p>
        ) : (
          <>
            <p style={{ margin: "0 0 6px", fontSize: 15, fontWeight: 600, color: colors.text }}>
              Drop a PDF, doc, or markdown file here
            </p>
            <p style={{ margin: 0, fontSize: 13, color: colors.muted }}>
              or{" "}
              <span style={{ textDecoration: "underline", color: colors.text }}>browse</span>
              {" "}· we'll re-index in ~30 seconds, no engineering ticket
            </p>
          </>
        )}
      </div>

      <input
        ref={inputRef}
        type="file"
        multiple
        style={{ display: "none" }}
        onChange={(e) => {
          if (e.target.files?.length) handleFiles(e.target.files);
          e.target.value = ""; // allow re-uploading the same file
        }}
      />

      {uploadError && (
        <div style={{ color: colors.errorFg, fontSize: 12, marginTop: 6 }}>{uploadError}</div>
      )}
    </div>
  );
}
