import React from "react";
import { colors, labelStyle } from "../../../student/styles/theme";
import { useAuditLog } from "../../hooks/useAuditLog";
import LogRow from "./LogRow";

const INTENT_OPTIONS = [
  { value: "",               label: "All intents" },
  { value: "curriculum",     label: "Curriculum" },
  { value: "answer_seeking", label: "Answer-seeking" },
  { value: "off_topic",      label: "Off-topic" },
];

// Paginated, filterable table of all recorded student interactions.
// Click any row to expand the full student + Pathwise message pair.
export default function AuditLogPage() {
  const log = useAuditLog();

  return (
    <div style={{ padding: "28px 32px", maxWidth: 900 }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: colors.text }}>Audit Log</h1>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: colors.muted }}>
            {log.total} interactions total
          </p>
        </div>

        {/* Intent filter */}
        <select
          value={log.intentFilter}
          onChange={(e) => log.changeIntent(e.target.value)}
          style={{
            background: colors.surface,
            border: `1px solid ${colors.border}`,
            borderRadius: 6,
            padding: "7px 12px",
            fontSize: 13,
            color: colors.text,
            cursor: "pointer",
            outline: "none",
          }}
        >
          {INTENT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {log.error && (
        <div style={{
          background: colors.errorBg, color: colors.errorFg,
          border: `1px solid ${colors.errorFg}`,
          borderRadius: 6, padding: "10px 14px", marginBottom: 16, fontSize: 13,
        }}>
          {log.error}
        </div>
      )}

      <div style={{
        background: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: 8,
        overflow: "hidden",
      }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${colors.border}` }}>
              {["Time", "Session", "Intent", "Attempt", "Student message"].map((h) => (
                <th key={h} style={{
                  padding: "9px 14px",
                  textAlign: "left",
                  ...labelStyle,
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {log.loading ? (
              <tr>
                <td colSpan={5} style={{ padding: "20px 14px", color: colors.muted, fontSize: 13 }}>
                  Loading…
                </td>
              </tr>
            ) : log.entries.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ padding: "20px 14px", color: colors.muted, fontSize: 13 }}>
                  No entries found.
                </td>
              </tr>
            ) : (
              log.entries.map((entry) => (
                <LogRow key={entry.log_id} entry={entry} />
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {log.totalPages > 1 && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 8, marginTop: 14 }}>
          <button
            onClick={() => log.setPage((p) => Math.max(1, p - 1))}
            disabled={log.page <= 1}
            style={{
              background: "transparent",
              border: `1px solid ${colors.border}`,
              borderRadius: 6,
              padding: "6px 14px",
              fontSize: 13,
              color: log.page <= 1 ? colors.border : colors.text,
              cursor: log.page <= 1 ? "not-allowed" : "pointer",
            }}
          >
            ← Prev
          </button>
          <span style={{ fontSize: 13, color: colors.muted }}>
            {log.page} / {log.totalPages}
          </span>
          <button
            onClick={() => log.setPage((p) => Math.min(log.totalPages, p + 1))}
            disabled={log.page >= log.totalPages}
            style={{
              background: "transparent",
              border: `1px solid ${colors.border}`,
              borderRadius: 6,
              padding: "6px 14px",
              fontSize: 13,
              color: log.page >= log.totalPages ? colors.border : colors.text,
              cursor: log.page >= log.totalPages ? "not-allowed" : "pointer",
            }}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
