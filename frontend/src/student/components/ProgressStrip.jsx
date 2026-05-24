import React from "react";
import { colors, labelStyle } from "../styles/theme";

// Horizontal strip of unit pill buttons for quick navigation between questions.
// Active pill uses accent color; completed pills show a checkmark.
export default function ProgressStrip({ questions, qIndex, completed, unitComplete, onJump }) {
  return (
    <div style={{
      background: colors.surface,
      border: `1px solid ${colors.border}`,
      borderRadius: 8,
      padding: "10px 16px",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      flexShrink: 0,
    }}>
      <div style={{ display: "flex", gap: 6 }}>
        {questions.map((q, index) => {
          const active = index === qIndex && !unitComplete;
          const done = completed.includes(index);
          return (
            <button
              key={index}
              onClick={() => onJump(index)}
              style={{
                padding: "4px 14px",
                borderRadius: 20,
                border: `1px solid ${active ? colors.accent : done ? colors.successFg : colors.border}`,
                background: active ? colors.accent : done ? colors.successBg : "transparent",
                color: active ? colors.accentText : done ? colors.successFg : colors.muted,
                fontWeight: 700,
                fontSize: 12,
                cursor: "pointer",
                letterSpacing: "0.3px",
                transition: "all 0.15s",
              }}
            >
              {done ? `✓ ${q.unit}` : q.unit}
            </button>
          );
        })}
      </div>
      <span style={{ ...labelStyle, letterSpacing: "0.5px" }}>
        {completed.length} of {questions.length} complete
      </span>
    </div>
  );
}
