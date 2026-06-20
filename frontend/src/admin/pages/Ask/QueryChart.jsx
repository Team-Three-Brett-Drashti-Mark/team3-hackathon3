import React from "react";
import { colors } from "../../../student/styles/theme";

// Auto-visualizer for Ask query results. The backend's suggest_viz() decides the
// shape ("bar" | "line" | "table"); this component renders it.
//
// Readability notes:
//   * Bar charts are drawn with real HTML/CSS (not SVG). An SVG that scales to
//     container width also scales its font DOWN, which is why the old charts were
//     unreadable. CSS bars use real pixel fonts that stay crisp and legible, and
//     horizontal bars give long category labels (intents, "Attempt 1+") room to
//     breathe instead of cramming them under thin vertical bars.
//   * The line chart (for time series) stays SVG since it needs a continuous axis,
//     but uses a taller canvas and larger fonts.
//
// Expected props mirror the /admin/ask payload:
//   columns: ["label", "count"]
//   rows:    [["curriculum", 42], ...]
//   viz:     "bar" | "line" | "table"

function EmptyState({ message }) {
  return (
    <div style={{
      padding: "24px 0", display: "flex", alignItems: "center", justifyContent: "center",
      color: colors.muted, fontSize: 14,
    }}>
      {message}
    </div>
  );
}

// Horizontal CSS bar chart — the readable default for categorical data.
function BarChart({ points }) {
  const max = Math.max(...points.map((p) => p.value), 1);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {points.map((p, i) => (
        <div
          key={i}
          style={{
            display: "grid",
            // Fixed label gutter + flexible bar track. The gutter is wide enough
            // for typical labels and truncates the rest with an ellipsis.
            gridTemplateColumns: "minmax(90px, 160px) 1fr",
            alignItems: "center",
            gap: 14,
          }}
        >
          <div
            title={String(p.label)}
            style={{
              fontSize: 14, fontWeight: 600, color: colors.text, textAlign: "right",
              overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
            }}
          >
            {p.label}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div
              style={{
                height: 26,
                width: `${Math.max((p.value / max) * 100, 1)}%`,
                minWidth: 3,
                background: colors.accent,
                borderRadius: 5,
                transition: "width 0.35s ease",
              }}
            />
            <span style={{ fontSize: 15, fontWeight: 800, color: colors.text, fontFamily: "ui-monospace, Consolas, monospace" }}>
              {p.value}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

// SVG line chart for time series. Larger fonts + taller canvas than before.
const LW = 640, LH = 280;
const LPAD = { top: 24, right: 24, bottom: 48, left: 52 };
const LCHART_W = LW - LPAD.left - LPAD.right;
const LCHART_H = LH - LPAD.top - LPAD.bottom;

function _short(label) {
  const s = String(label ?? "");
  return s.length > 12 ? `${s.slice(0, 11)}…` : s;
}

function LineChart({ points }) {
  // A single point can't form a line — fall back to a bar so it's still visible.
  if (points.length === 1) return <BarChart points={points} />;

  const max = Math.max(...points.map((p) => p.value), 1);
  const stepX = LCHART_W / (points.length - 1);
  const coords = points.map((p, i) => ({
    ...p,
    x: LPAD.left + i * stepX,
    y: LPAD.top + LCHART_H - (p.value / max) * LCHART_H,
  }));
  const path = coords.map((c, i) => `${i === 0 ? "M" : "L"} ${c.x} ${c.y}`).join(" ");
  // Thin out x labels when there are many points so they don't overlap.
  const labelEvery = Math.ceil(points.length / 8);

  return (
    <svg viewBox={`0 0 ${LW} ${LH}`} style={{ width: "100%", height: "auto", display: "block" }}>
      {/* Y gridlines + ticks */}
      {[0, 0.25, 0.5, 0.75, 1].map((pct) => {
        const y = LPAD.top + LCHART_H * (1 - pct);
        return (
          <g key={pct}>
            <line x1={LPAD.left} y1={y} x2={LPAD.left + LCHART_W} y2={y} stroke={colors.border} strokeWidth={0.75} />
            <text x={LPAD.left - 8} y={y + 4} textAnchor="end" fontSize={13} fill={colors.muted}>
              {Math.round(max * pct)}
            </text>
          </g>
        );
      })}
      <path d={path} fill="none" stroke={colors.text} strokeWidth={2.5} />
      {coords.map((c, i) => (
        <g key={i}>
          <circle cx={c.x} cy={c.y} r={4} fill={colors.accent} stroke={colors.text} strokeWidth={1.5} />
          {i % labelEvery === 0 && (
            <text x={c.x} y={LPAD.top + LCHART_H + 22} textAnchor="middle" fontSize={13} fill={colors.muted}>
              {_short(c.label)}
            </text>
          )}
        </g>
      ))}
      <line x1={LPAD.left} y1={LPAD.top + LCHART_H} x2={LPAD.left + LCHART_W} y2={LPAD.top + LCHART_H}
            stroke={colors.border} strokeWidth={1.5} />
    </svg>
  );
}

function ResultTable({ columns, rows }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
        <thead>
          <tr>
            {columns.map((c, i) => (
              <th key={i} style={{
                textAlign: "left", padding: "10px 14px", borderBottom: `2px solid ${colors.border}`,
                color: colors.muted, fontWeight: 700, whiteSpace: "nowrap",
              }}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, ri) => (
            // Zebra striping so dense result tables stay scannable.
            <tr key={ri} style={{ background: ri % 2 ? colors.editor : "transparent" }}>
              {r.map((cell, ci) => (
                <td key={ci} style={{
                  padding: "10px 14px", borderBottom: `1px solid ${colors.border}`, color: colors.text,
                }}>
                  {String(cell ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function QueryChart({ columns = [], rows = [], viz = "table" }) {
  if (!rows.length) return <EmptyState message="No rows returned." />;

  // For bar/line we need a [label, numericValue] shape. Build it defensively:
  // anything that doesn't parse as a number falls back to the table so we never
  // render a broken/empty chart.
  if (viz === "bar" || viz === "line") {
    const points = rows.map((r) => ({ label: r[0], value: Number(r[1]) }));
    const allNumeric = points.every((p) => Number.isFinite(p.value));
    if (allNumeric) {
      return viz === "line" ? <LineChart points={points} /> : <BarChart points={points} />;
    }
  }

  return <ResultTable columns={columns} rows={rows} />;
}
