import React, { useState } from "react";
import { colors } from "../../../student/styles/theme";

// Inline modal for naming and creating a new curriculum week.
// Calls onConfirm(name) and awaits it — shows an error if it throws.
export default function NewWeekModal({ onConfirm, onCancel }) {
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    setSubmitting(true);
    setError(null);
    try {
      await onConfirm(trimmed);
    } catch (e) {
      setError(e.message);
      setSubmitting(false);
    }
  };

  return (
    // Backdrop
    <div
      onClick={onCancel}
      style={{
        position: "fixed", inset: 0, zIndex: 50,
        background: "rgba(0,0,0,0.25)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
    >
      {/* Dialog — stop click from closing via backdrop */}
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: colors.surface,
          border: `1px solid ${colors.border}`,
          borderRadius: 10,
          padding: 28,
          width: 360,
          boxShadow: "0 8px 32px rgba(0,0,0,0.12)",
        }}
      >
        <h2 style={{ margin: "0 0 6px", fontSize: 17, fontWeight: 700, color: colors.text }}>
          New week
        </h2>
        <p style={{ margin: "0 0 18px", fontSize: 13, color: colors.muted }}>
          Creates a folder with <code>markdown/</code>, <code>pdfs/</code>, and <code>quizzes/</code> inside it.
        </p>

        <input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") handleSubmit(); if (e.key === "Escape") onCancel(); }}
          placeholder="e.g. week_2"
          style={{
            width: "100%",
            boxSizing: "border-box",
            background: colors.bg,
            border: `1px solid ${colors.border}`,
            borderRadius: 6,
            color: colors.text,
            padding: "9px 12px",
            fontSize: 14,
            outline: "none",
            fontFamily: "Inter, system-ui, sans-serif",
            marginBottom: error ? 8 : 16,
          }}
        />

        {error && (
          <div style={{ color: colors.errorFg, fontSize: 12, marginBottom: 12 }}>{error}</div>
        )}

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button
            onClick={onCancel}
            style={{
              background: "transparent",
              border: `1px solid ${colors.border}`,
              borderRadius: 6,
              padding: "8px 16px",
              fontSize: 13,
              color: colors.muted,
              cursor: "pointer",
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!name.trim() || submitting}
            style={{
              background: colors.accent,
              border: "none",
              borderRadius: 6,
              padding: "8px 18px",
              fontSize: 13,
              fontWeight: 700,
              color: colors.accentText,
              cursor: !name.trim() || submitting ? "not-allowed" : "pointer",
              opacity: !name.trim() || submitting ? 0.5 : 1,
            }}
          >
            {submitting ? "Creating…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}
