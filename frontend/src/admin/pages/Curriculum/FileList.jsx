import React from "react";
import { colors, labelStyle } from "../../../student/styles/theme";

function formatBytes(bytes) {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric",
  });
}

// Table of files in the selected folder with size, date, and a delete action.
//
// Props:
//   files        — array from the backend's GET /admin/curriculum/weeks/.../...
//                  Each entry: { name, path, size_bytes, last_modified }.
//   loading      — show a placeholder while the parent is fetching.
//   onDelete     — bound to handleDelete in CurriculumPage, which prompts for
//                  confirmation before kicking off the cascade.
//   disabledPath — bronze path of the file whose cascade is currently
//                  in-flight (sourced from useCurriculum's deleteStatus.path).
//                  We compare per-row against file.path so only that row's
//                  button dims and shows "removing…". Why disable instead of
//                  just trust the user: the cold-warehouse cascade can take
//                  ~60s, plenty of time for an impatient user to click again
//                  and queue a redundant request.
export default function FileList({ files, loading, onDelete, disabledPath }) {
  if (loading) {
    return <div style={{ color: colors.muted, fontSize: 13, padding: "8px 0" }}>Loading files…</div>;
  }

  if (!files.length) {
    return (
      <div style={{ color: colors.muted, fontSize: 13, padding: "8px 0" }}>
        No files yet — drop something above.
      </div>
    );
  }

  return (
    <div style={{
      background: colors.surface,
      border: `1px solid ${colors.border}`,
      borderRadius: 8,
      overflow: "hidden",
    }}>
      <div style={{
        display: "grid",
        gridTemplateColumns: "1fr 80px 120px 60px",
        padding: "8px 16px",
        borderBottom: `1px solid ${colors.border}`,
        ...labelStyle,
        gap: 8,
      }}>
        <span>File</span>
        <span>Size</span>
        <span>Updated</span>
        <span />
      </div>

      {files.map((file, i) => {
        // True only for the single in-flight row, because disabledPath holds
        // exactly one bronze path at a time (or null when idle). Drives the
        // row opacity, button label, button cursor, and the hover guards on
        // the remove button.
        const isDeleting = disabledPath === file.path;
        return (
          <div
            key={file.path}
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 80px 120px 60px",
              padding: "11px 16px",
              borderBottom: i < files.length - 1 ? `1px solid ${colors.border}` : "none",
              alignItems: "center",
              gap: 8,
              // Half-fade the row to communicate "this is going away" without
              // ripping it out of the DOM mid-cascade. Keeps the surrounding
              // rows from shifting and lets the user keep track of which file
              // they clicked while the toast above shows the same name.
              opacity: isDeleting ? 0.5 : 1,
              transition: "opacity 0.15s",
            }}
          >
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: colors.text }}>{file.name}</div>
            </div>
            <div style={{ fontSize: 12, color: colors.muted }}>{formatBytes(file.size_bytes)}</div>
            <div style={{ fontSize: 12, color: colors.muted }}>{formatDate(file.last_modified)}</div>
            <button
              onClick={() => onDelete(file.path)}
              // disabled blocks the click event entirely — important because
              // the cascade is destructive and isn't safe to fire twice on
              // the same file (silver/vector deletes are idempotent but the
              // bronze step would error on the second click).
              disabled={isDeleting}
              style={{
                background: "transparent",
                border: `1px solid ${colors.border}`,
                borderRadius: 4,
                padding: "3px 8px",
                fontSize: 11,
                color: colors.muted,
                cursor: isDeleting ? "not-allowed" : "pointer",
              }}
              // Hover handlers short-circuit while in-flight so the button
              // doesn't flash the red "destructive action" styling that would
              // suggest it's still clickable.
              onMouseEnter={(e) => {
                if (isDeleting) return;
                e.currentTarget.style.borderColor = colors.errorFg;
                e.currentTarget.style.color = colors.errorFg;
              }}
              onMouseLeave={(e) => {
                if (isDeleting) return;
                e.currentTarget.style.borderColor = colors.border;
                e.currentTarget.style.color = colors.muted;
              }}
            >
              {isDeleting ? "removing…" : "remove"}
            </button>
          </div>
        );
      })}

      <div style={{ padding: "8px 16px", fontSize: 12, color: colors.muted }}>
        You'll never need to file a ticket to change a file. Promise.
      </div>
    </div>
  );
}
