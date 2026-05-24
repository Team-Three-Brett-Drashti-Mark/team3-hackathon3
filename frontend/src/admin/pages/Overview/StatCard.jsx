import React from "react";
import { colors } from "../../../student/styles/theme";

// Metric tile: large number + label + optional highlight for warning states.
export default function StatCard({ label, value, highlight = false, loading = false }) {
  return (
    <div style={{
      background: colors.surface,
      border: `1px solid ${highlight ? colors.errorFg : colors.border}`,
      borderRadius: 8,
      padding: "18px 22px",
      display: "flex",
      flexDirection: "column",
      gap: 4,
      minWidth: 140,
      // Dashed border for highlighted "needs attention" cards, matching the reference
      borderStyle: highlight ? "dashed" : "solid",
    }}>
      <div style={{
        fontSize: 36,
        fontWeight: 800,
        color: highlight ? colors.errorFg : colors.text,
        lineHeight: 1,
        fontFamily: "ui-monospace, Consolas, monospace",
      }}>
        {loading ? "—" : value}
      </div>
      <div style={{ fontSize: 13, color: colors.muted, lineHeight: 1.4 }}>
        {label}
      </div>
    </div>
  );
}
