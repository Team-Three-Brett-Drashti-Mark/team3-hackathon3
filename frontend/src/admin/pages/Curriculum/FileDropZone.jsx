import React, { useState, useRef } from "react";
import { colors } from "../../../student/styles/theme";

// Drag-and-drop + click-to-browse upload area.
// Calls onUpload(File) for each dropped/selected file sequentially.
//
// Two reasons we might refuse to accept a drop:
//   - `uploading` : a previous file's POST is still in flight. Short window
//                   (~seconds), set/cleared by the page on each upload call.
//   - `etlRunning`: the backend has fired the ETL job_run for an earlier
//                   upload and we're waiting for it to complete. Longer
//                   window (~30-90s) — surfaced as a separate flag so the
//                   message can explain WHY we're blocking ("ETL still
//                   indexing…") rather than just the generic "uploading…".
// Both share the disabled-visual treatment; only the placeholder text
// differs between them.
export default function FileDropZone({ onUpload, uploading, etlRunning }) {
  const disabled = uploading || etlRunning;
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
          if (!disabled) handleFiles(e.dataTransfer.files);
        }}
        onClick={() => !disabled && inputRef.current?.click()}
        style={{
          border: `2px dashed ${dragging ? colors.accent : colors.border}`,
          borderRadius: 8,
          padding: "28px 24px",
          textAlign: "center",
          cursor: disabled ? "not-allowed" : "pointer",
          background: dragging ? `${colors.accent}11` : colors.surface,
          transition: "border-color 0.15s, background 0.15s",
          // Half-fade while the ETL is still indexing the previous upload so
          // the drop zone visibly reads as "not ready" — matches the row-
          // dimming pattern used by the cascade-delete in FileList.
          opacity: etlRunning && !uploading ? 0.6 : 1,
        }}
      >
        {uploading ? (
          <p style={{ margin: 0, fontSize: 13, color: colors.muted }}>Uploading…</p>
        ) : etlRunning ? (
          // Distinct copy from the "Uploading…" message above: this is the
          // longer wait, and naming the cause helps the admin understand
          // why a new drop is being refused. The actual ETL toast above the
          // file list shows the live progress.
          <p style={{ margin: 0, fontSize: 13, color: colors.muted }}>
            ETL still indexing the previous upload — drop zone re-enables when it finishes.
          </p>
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
