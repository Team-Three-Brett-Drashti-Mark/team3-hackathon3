import React, { useState } from "react";
import { colors } from "../styles/theme";

// Completion screen shown in place of the question panel after all questions pass.
export default function UnitComplete({ total, onRestart }) {
  const [hovered, setHovered] = useState(false);

  return (
    <div style={{
      background: colors.surface,
      border: `1px solid ${colors.border}`,
      borderRadius: 8,
      flex: 1,
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      gap: 16,
      padding: 32,
      textAlign: "center",
    }}>
      <div style={{
        width: 48, height: 48, borderRadius: "50%",
        background: colors.successBg,
        border: `2px solid ${colors.successFg}`,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 22, color: colors.successFg, fontWeight: 700,
      }}>
        ✓
      </div>
      <div>
        <div style={{ fontSize: 20, fontWeight: 700, color: colors.text, marginBottom: 8 }}>Unit Complete</div>
        <div style={{ fontSize: 14, color: colors.muted, lineHeight: 1.6 }}>
          You answered all {total} questions correctly.
        </div>
      </div>
      <button
        onClick={onRestart}
        style={{
          background: hovered ? "#d4a948" : colors.accent,
          color: colors.accentText,
          border: "none",
          borderRadius: 6,
          padding: "10px 24px",
          fontWeight: 700,
          fontSize: 14,
          cursor: "pointer",
          transition: "background 0.15s",
        }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        Start Over
      </button>
    </div>
  );
}
