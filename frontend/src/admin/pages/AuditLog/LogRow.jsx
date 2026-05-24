import React, { useState } from "react";
import { colors } from "../../../student/styles/theme";

const INTENT_COLORS = {
  curriculum:     { bg: colors.successBg, fg: colors.successFg },
  answer_seeking: { bg: colors.errorBg,   fg: colors.errorFg },
  off_topic:      { bg: colors.editor,    fg: colors.muted },
};

// Single row in the audit log table with an expandable message preview.
export default function LogRow({ entry }) {
  const [expanded, setExpanded] = useState(false);
  const meta = INTENT_COLORS[entry.intent] || { bg: colors.editor, fg: colors.muted };

  return (
    <>
      <tr
        onClick={() => setExpanded((v) => !v)}
        style={{ cursor: "pointer" }}
      >
        <td style={{ padding: "10px 14px", fontSize: 12, color: colors.muted, whiteSpace: "nowrap" }}>
          {new Date(entry.timestamp).toLocaleString("en-US", {
            month: "short", day: "numeric",
            hour: "2-digit", minute: "2-digit",
          })}
        </td>
        <td style={{ padding: "10px 14px", fontSize: 12, color: colors.muted, fontFamily: "ui-monospace, monospace" }}>
          {entry.session_id?.slice(0, 8)}…
        </td>
        <td style={{ padding: "10px 14px" }}>
          <span style={{
            background: meta.bg, color: meta.fg,
            borderRadius: 20, padding: "2px 10px", fontSize: 11, fontWeight: 700,
            whiteSpace: "nowrap",
          }}>
            {entry.intent}
          </span>
        </td>
        <td style={{ padding: "10px 14px", fontSize: 12, color: colors.muted, textAlign: "center" }}>
          {entry.attempt}
        </td>
        <td style={{ padding: "10px 14px", fontSize: 12, color: colors.text, maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {entry.user_input}
        </td>
      </tr>

      {/* Expandable detail row */}
      {expanded && (
        <tr style={{ background: colors.bg }}>
          <td colSpan={5} style={{ padding: "12px 14px" }}>
            <div style={{ marginBottom: 8 }}>
              <span style={{ ...{ fontSize: 10, fontWeight: 700, letterSpacing: "1px", textTransform: "uppercase", color: colors.muted } }}>Student</span>
              <pre style={{ margin: "4px 0 0", fontSize: 12, color: colors.text, whiteSpace: "pre-wrap", fontFamily: "Inter, system-ui, sans-serif" }}>
                {entry.user_input}
              </pre>
            </div>
            <div>
              <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "1px", textTransform: "uppercase", color: colors.muted }}>Pathwise</span>
              <pre style={{ margin: "4px 0 0", fontSize: 12, color: colors.muted, whiteSpace: "pre-wrap", fontFamily: "Inter, system-ui, sans-serif" }}>
                {entry.system_output}
              </pre>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
