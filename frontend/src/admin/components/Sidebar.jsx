import React from "react";
import { colors } from "../../student/styles/theme";

const NAV_ITEMS = [
  { id: "overview",   label: "Overview",   emoji: "📊" },
  { id: "curriculum", label: "Curriculum", emoji: "📚" },
  { id: "audit",      label: "Audit Log",  emoji: "🛡️" },
  { id: "ask",        label: "Ask",        emoji: "💬" },
];

// Left sidebar: branding + navigation. Stays fixed while content scrolls.
export default function Sidebar({ activePage, onNavigate }) {
  return (
    <div style={{
      width: 220,
      flexShrink: 0,
      background: colors.surface,
      borderRight: `1px solid ${colors.border}`,
      display: "flex",
      flexDirection: "column",
      height: "100vh",
      position: "sticky",
      top: 0,
    }}>
      {/* Brand */}
      <div style={{
        padding: "20px 18px 16px",
        borderBottom: `1px solid ${colors.border}`,
        display: "flex",
        alignItems: "center",
        gap: 10,
      }}>
        <div style={{
          width: 28, height: 28, borderRadius: 6,
          background: colors.accent,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 13, fontWeight: 900, color: colors.nav, flexShrink: 0,
        }}>
          P
        </div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: colors.text, lineHeight: 1.2 }}>
            Pathwise
          </div>
          <div style={{ fontSize: 11, color: colors.muted }}>admin</div>
        </div>
      </div>

      {/* Nav items */}
      <nav style={{ padding: "10px 10px", display: "flex", flexDirection: "column", gap: 2 }}>
        {NAV_ITEMS.map((item) => {
          const active = activePage === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "9px 12px",
                borderRadius: 6,
                border: "none",
                background: active ? colors.text : "transparent",
                color: active ? colors.navText : colors.muted,
                fontWeight: active ? 700 : 500,
                fontSize: 14,
                cursor: "pointer",
                textAlign: "left",
                width: "100%",
                transition: "background 0.1s, color 0.1s",
              }}
            >
              <span style={{ fontSize: 16 }}>{item.emoji}</span>
              {item.label}
            </button>
          );
        })}
      </nav>
    </div>
  );
}
