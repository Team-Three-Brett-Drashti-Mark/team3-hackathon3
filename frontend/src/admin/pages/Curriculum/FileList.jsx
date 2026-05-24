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
export default function FileList({ files, loading, onDelete }) {
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

      {files.map((file, i) => (
        <div
          key={file.path}
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 80px 120px 60px",
            padding: "11px 16px",
            borderBottom: i < files.length - 1 ? `1px solid ${colors.border}` : "none",
            alignItems: "center",
            gap: 8,
          }}
        >
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: colors.text }}>{file.name}</div>
          </div>
          <div style={{ fontSize: 12, color: colors.muted }}>{formatBytes(file.size_bytes)}</div>
          <div style={{ fontSize: 12, color: colors.muted }}>{formatDate(file.last_modified)}</div>
          <button
            onClick={() => onDelete(file.path)}
            style={{
              background: "transparent",
              border: `1px solid ${colors.border}`,
              borderRadius: 4,
              padding: "3px 8px",
              fontSize: 11,
              color: colors.muted,
              cursor: "pointer",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = colors.errorFg; e.currentTarget.style.color = colors.errorFg; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = colors.border; e.currentTarget.style.color = colors.muted; }}
          >
            remove
          </button>
        </div>
      ))}

      <div style={{ padding: "8px 16px", fontSize: 12, color: colors.muted }}>
        You'll never need to file a ticket to change a file. Promise.
      </div>
    </div>
  );
}
