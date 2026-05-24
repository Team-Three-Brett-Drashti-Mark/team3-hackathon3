import React from "react";
import { colors } from "../../../student/styles/theme";

// Intent labels and colors for the three classifier outcomes.
const INTENT_META = {
  curriculum:     { label: "Curriculum",      color: colors.accent },
  answer_seeking: { label: "Answer-seeking",  color: colors.errorFg },
  off_topic:      { label: "Off-topic",       color: colors.muted },
};

// Horizontal bar chart showing question distribution by intent.
// Simpler than the daily chart — three fixed rows, no axes needed.
export default function IntentBreakdownChart({ data = [] }) {
  const total = data.reduce((s, d) => s + d.count, 0) || 1;

  if (!data.length) {
    return (
      <div style={{ color: colors.muted, fontSize: 13, padding: "8px 0" }}>
        No data yet
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {data.map((d) => {
        const meta = INTENT_META[d.intent] || { label: d.intent, color: colors.muted };
        const pct = Math.round((d.count / total) * 100);
        return (
          <div key={d.intent}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: 12 }}>
              <span style={{ color: colors.text, fontWeight: 600 }}>{meta.label}</span>
              <span style={{ color: colors.muted }}>{d.count} ({pct}%)</span>
            </div>
            <div style={{
              height: 8,
              background: colors.border,
              borderRadius: 4,
              overflow: "hidden",
            }}>
              <div style={{
                width: `${pct}%`,
                height: "100%",
                background: meta.color,
                borderRadius: 4,
                transition: "width 0.3s ease",
              }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
