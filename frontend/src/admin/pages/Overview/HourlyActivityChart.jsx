import React from "react";
import { colors } from "../../../student/styles/theme";

const W = 520, H = 120;
const PAD = { top: 10, right: 16, bottom: 28, left: 30 };
const CHART_W = W - PAD.left - PAD.right;
const CHART_H = H - PAD.top - PAD.bottom;

// Bar chart showing question volume by hour of day (0–23).
// Helps admins spot peak usage windows for scheduling office hours, etc.
export default function HourlyActivityChart({ data = [] }) {
  if (!data.length) {
    return (
      <div style={{ height: H, display: "flex", alignItems: "center", justifyContent: "center", color: colors.muted, fontSize: 13 }}>
        No data yet
      </div>
    );
  }

  // Fill all 24 hours so gaps show as zero bars.
  const byHour = Object.fromEntries(data.map((d) => [d.hour, d.count]));
  const full = Array.from({ length: 24 }, (_, h) => ({ hour: h, count: byHour[h] ?? 0 }));
  const maxCount = Math.max(...full.map((d) => d.count), 1);

  const barSlot = CHART_W / 24;
  const barW = Math.max(barSlot * 0.65, 2);

  // Label every 6 hours so the axis isn't crowded.
  const hourLabel = (h) => {
    if (h === 0) return "12a";
    if (h === 12) return "12p";
    return h < 12 ? `${h}a` : `${h - 12}p`;
  };

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
      {/* Bars */}
      {full.map((d) => {
        const barH = (d.count / maxCount) * CHART_H;
        const x = PAD.left + d.hour * barSlot + (barSlot - barW) / 2;
        const y = PAD.top + CHART_H - barH;
        return (
          <rect
            key={d.hour}
            x={x} y={y} width={barW} height={Math.max(barH, 1)}
            rx={1} ry={1}
            fill={d.count > 0 ? colors.accent : colors.border}
          />
        );
      })}

      {/* X-axis baseline */}
      <line
        x1={PAD.left} y1={PAD.top + CHART_H}
        x2={PAD.left + CHART_W} y2={PAD.top + CHART_H}
        stroke={colors.border} strokeWidth={1}
      />

      {/* Hour labels every 6 hours */}
      {[0, 6, 12, 18].map((h) => {
        const x = PAD.left + h * barSlot + barSlot / 2;
        return (
          <text key={h} x={x} y={PAD.top + CHART_H + 14} textAnchor="middle" fontSize={9} fill={colors.muted}>
            {hourLabel(h)}
          </text>
        );
      })}
    </svg>
  );
}
