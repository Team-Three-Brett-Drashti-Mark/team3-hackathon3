import React from "react";
import { colors, labelStyle } from "../styles/theme";

// Top navigation bar: branding, current unit subtitle, and a live progress badge.
export default function Navbar({ pageSubtitle, completedCount, totalCount }) {
  return (
    <div style={{
      height: 52,
      background: colors.nav,
      borderBottom: `2px solid ${colors.accent}`,
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      padding: "0 20px",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{
          width: 28, height: 28, borderRadius: 6,
          background: colors.accent,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 13, fontWeight: 900, color: colors.nav, flexShrink: 0,
        }}>
          P
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
          <span style={{ color: colors.navText, fontWeight: 700, fontSize: 15 }}>Pathwise</span>
          <span style={{ color: colors.muted, fontSize: 13 }}>·</span>
          <span style={{ color: colors.muted, fontSize: 13 }}>{pageSubtitle}</span>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ ...labelStyle, color: colors.muted }}>Progress</span>
        <span style={{
          fontSize: 13, fontWeight: 700, color: colors.accent,
          background: "rgba(236,192,88,0.1)",
          border: "1px solid rgba(236,192,88,0.25)",
          padding: "3px 10px", borderRadius: 20,
        }}>
          {completedCount} / {totalCount}
        </span>
      </div>
    </div>
  );
}
