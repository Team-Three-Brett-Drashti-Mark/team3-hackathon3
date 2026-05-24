import React from "react";
import { colors, labelStyle } from "../../../student/styles/theme";

// Displays the top-level list of curriculum weeks as clickable rows.
export default function WeekList({ weeks, loading, onSelect, onNewWeek }) {
  if (loading) {
    return <div style={{ color: colors.muted, fontSize: 13, padding: "12px 0" }}>Loading weeks…</div>;
  }

  return (
    <div>
      {weeks.length === 0 ? (
        <div style={{
          border: `1px dashed ${colors.border}`,
          borderRadius: 8,
          padding: "28px 24px",
          color: colors.muted,
          fontSize: 13,
          textAlign: "center",
          marginBottom: 16,
        }}>
          No weeks found in the curriculum volume.
        </div>
      ) : (
        <div style={{
          background: colors.surface,
          border: `1px solid ${colors.border}`,
          borderRadius: 8,
          overflow: "hidden",
          marginBottom: 16,
        }}>
          <div style={{
            padding: "10px 16px",
            borderBottom: `1px solid ${colors.border}`,
            ...labelStyle,
          }}>
            Curriculum library
          </div>
          {weeks.map((week, i) => (
            <div
              key={week.name}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "12px 16px",
                borderBottom: i < weeks.length - 1 ? `1px solid ${colors.border}` : "none",
                cursor: "pointer",
              }}
              onClick={() => onSelect(week.name)}
            >
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: colors.text }}>
                  📁 {week.name}
                </div>
                <div style={{ fontSize: 12, color: colors.muted, marginTop: 2 }}>
                  markdown · pdfs · quizzes
                </div>
              </div>
              <span style={{ color: colors.muted, fontSize: 18 }}>›</span>
            </div>
          ))}
        </div>
      )}

      <button
        onClick={onNewWeek}
        style={{
          background: colors.accent,
          border: "none",
          borderRadius: 6,
          padding: "10px 20px",
          fontSize: 13,
          fontWeight: 700,
          color: colors.accentText,
          cursor: "pointer",
        }}
      >
        + New week
      </button>
    </div>
  );
}
