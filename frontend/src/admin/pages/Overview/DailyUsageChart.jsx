import React from "react";
import { colors } from "../../../student/styles/theme";

const W = 520, H = 160;
const PAD = { top: 10, right: 16, bottom: 36, left: 36 };
const CHART_W = W - PAD.left - PAD.right;
const CHART_H = H - PAD.top - PAD.bottom;

// Inline SVG bar chart showing question counts for the past 7 days.
// No chart library dependency — keeps the bundle small.
export default function DailyUsageChart({ data = [] }) {
  if (!data.length) {
    return (
      <div style={{ height: H, display: "flex", alignItems: "center", justifyContent: "center", color: colors.muted, fontSize: 13 }}>
        No data yet
      </div>
    );
  }

  const maxCount = Math.max(...data.map((d) => d.count), 1);
  const barSlot = CHART_W / data.length;
  const barW = Math.max(barSlot * 0.55, 4);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
      {/* Y-axis gridlines */}
      {[0, 0.25, 0.5, 0.75, 1].map((pct) => {
        const y = PAD.top + CHART_H * (1 - pct);
        const val = Math.round(maxCount * pct);
        return (
          <g key={pct}>
            <line
              x1={PAD.left} y1={y} x2={PAD.left + CHART_W} y2={y}
              stroke={colors.border} strokeWidth={0.5}
            />
            <text x={PAD.left - 6} y={y + 4} textAnchor="end" fontSize={9} fill={colors.muted}>
              {val}
            </text>
          </g>
        );
      })}

      {/* Bars */}
      {data.map((d, i) => {
        const barH = (d.count / maxCount) * CHART_H;
        const x = PAD.left + i * barSlot + (barSlot - barW) / 2;
        const y = PAD.top + CHART_H - barH;
        const [, mm, dd] = (d.date || "").split("-");
        const label = d.date ? `${parseInt(mm)}/${parseInt(dd)}` : "";

        return (
          <g key={i}>
            <rect
              x={x} y={y} width={barW} height={Math.max(barH, 1)}
              rx={2} ry={2}
              fill={d.count > 0 ? colors.text : colors.border}
            />
            {/* Count label above bar */}
            {d.count > 0 && (
              <text x={x + barW / 2} y={y - 4} textAnchor="middle" fontSize={9} fill={colors.muted}>
                {d.count}
              </text>
            )}
            {/* Date label below bar */}
            <text
              x={x + barW / 2}
              y={PAD.top + CHART_H + 16}
              textAnchor="middle"
              fontSize={9}
              fill={colors.muted}
            >
              {label}
            </text>
          </g>
        );
      })}

      {/* X-axis baseline */}
      <line
        x1={PAD.left} y1={PAD.top + CHART_H}
        x2={PAD.left + CHART_W} y2={PAD.top + CHART_H}
        stroke={colors.border} strokeWidth={1}
      />
    </svg>
  );
}
