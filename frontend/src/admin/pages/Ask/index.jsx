import React, { useEffect, useState } from "react";
import { colors, labelStyle } from "../../../student/styles/theme";
import { askQuestion, fetchDashboard } from "../../services/adminApi";
import QueryChart from "./QueryChart";

// Natural-language query interface over the interaction logs. An admin asks a
// question in plain English; the backend (app/ask_agent.py) guards scope strictly
// to the logging tables, generates + validates read-only SQL, runs it, and returns
// a narrated answer plus rows we auto-chart here.

// Example prompts double as documentation of what's in scope — clicking one fills
// the box so first-time admins immediately see the kind of question that works.
const EXAMPLES = [
  "How many off-topic questions were asked this week?",
  "What hours of the day see the most activity?",
  "Break down interactions by intent.",
  "How many sessions reached attempt 3?",
];

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showSql, setShowSql] = useState(false);
  // Monotonic id bumped on every successful query. We use it as the React `key`
  // on the chart wrapper so the chart fully unmounts and remounts each time a new
  // question is answered — guaranteeing a fresh render even when the new result
  // has the same shape as the previous one (per the "rerender every question"
  // requirement). Without a changing key, React would diff-and-reuse the old SVG.
  const [runId, setRunId] = useState(0);

  const [dashboard, setDashboard] = useState(null);

  // Load the compact log dashboard once on mount. It's independent of whatever the
  // admin asks, so it renders immediately and gives the page context even before
  // the first question.
  useEffect(() => {
    fetchDashboard()
      .then(setDashboard)
      .catch(() => setDashboard(null)); // non-fatal: the Ask box still works
  }, []);

  async function submit(q) {
    const text = (q ?? question).trim();
    if (!text || loading) return;
    setLoading(true);
    setError("");
    try {
      const payload = await askQuestion(text);
      setResult(payload);
      setShowSql(false);
      setRunId((n) => n + 1); // force a fresh chart mount for this answer
    } catch (e) {
      setError(e.message || "Something went wrong.");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  function onExample(ex) {
    setQuestion(ex);
    submit(ex);
  }

  // A single-value result (one row, one column) is fully captured by the prose
  // answer (e.g. "42 off-topic questions were asked"). Rendering a one-cell table
  // for it just exposes the raw SQL column alias (like "n") as a label, which adds
  // nothing and looks technical — so we suppress the chart/table in that case and
  // let the answer text stand alone. Multi-row results still chart/table as usual.
  const isScalarResult =
    !!result && !result.refused &&
    result.rows?.length === 1 && result.columns?.length === 1;

  return (
    <div style={{ padding: "28px 32px", maxWidth: 860 }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: 28, fontWeight: 800, color: colors.text }}>Ask</h1>
        <p style={{ margin: "6px 0 0", fontSize: 15, color: colors.muted, lineHeight: 1.6 }}>
          Ask questions about student interaction patterns in plain English.
          Answers come only from the interaction logs.
        </p>
      </div>

      {/* Compact log dashboard — always-on context above the query box */}
      {dashboard && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 28 }}>
          <DashboardCard title="Escalation funnel" data={dashboard.escalation_funnel} />
          <DashboardCard title="Attempts distribution" data={dashboard.attempt_distribution} />
        </div>
      )}

      {/* Query box */}
      <form
        onSubmit={(e) => { e.preventDefault(); submit(); }}
        style={{ display: "flex", gap: 10, marginBottom: 14 }}
      >
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. How many off-topic questions were asked this week?"
          style={{
            flex: 1,
            padding: "14px 16px",
            borderRadius: 10,
            border: `1px solid ${colors.border}`,
            background: colors.surface,
            color: colors.text,
            fontSize: 16,
            outline: "none",
          }}
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          style={{
            padding: "14px 28px",
            borderRadius: 10,
            border: "none",
            background: colors.text,
            color: colors.navText,
            fontSize: 16,
            fontWeight: 700,
            cursor: loading || !question.trim() ? "default" : "pointer",
            opacity: loading || !question.trim() ? 0.5 : 1,
          }}
        >
          {loading ? "Asking…" : "Ask"}
        </button>
      </form>

      {/* Example prompts */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 28 }}>
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            onClick={() => onExample(ex)}
            disabled={loading}
            style={{
              padding: "8px 14px",
              borderRadius: 999,
              border: `1px solid ${colors.border}`,
              background: "transparent",
              color: colors.muted,
              fontSize: 13,
              cursor: loading ? "default" : "pointer",
            }}
          >
            {ex}
          </button>
        ))}
      </div>

      {error && (
        <div style={{
          background: colors.errorBg, color: colors.errorFg,
          border: `1px solid ${colors.errorFg}`,
          borderRadius: 6, padding: "10px 14px", marginBottom: 20, fontSize: 13,
        }}>
          {error}
        </div>
      )}

      {/* Answer + chart */}
      {result && (
        <div style={{
          background: colors.surface,
          border: `1px solid ${colors.border}`,
          borderRadius: 10,
          padding: "24px 26px",
        }}>
          <p style={{ margin: 0, fontSize: 17, color: colors.text, lineHeight: 1.65 }}>
            {result.answer}
          </p>

          {/* Auto-chart. Keyed by runId so each answer gets a brand-new mount. */}
          {!result.refused && result.rows?.length > 0 && !isScalarResult && (
            <div key={runId} style={{ marginTop: 18 }}>
              <QueryChart columns={result.columns} rows={result.rows} viz={result.viz} />
            </div>
          )}

          {/* View SQL — transparency toggle so admins can see (and trust) exactly
              what ran. Also shown when a query was generated but REFUSED at
              validation, so the attempted SQL is visible for debugging instead of
              swallowed behind a generic "couldn't build a safe query" message. */}
          {result.sql && (
            <div style={{ marginTop: 16 }}>
              <button
                onClick={() => setShowSql((s) => !s)}
                style={{
                  background: "transparent", border: "none", padding: 0,
                  color: colors.muted, fontSize: 13, cursor: "pointer", textDecoration: "underline",
                }}
              >
                {showSql
                  ? (result.refused ? "Hide attempted SQL" : "Hide SQL")
                  : (result.refused ? "View attempted SQL" : "View SQL")}
              </button>
              {showSql && (
                <pre style={{
                  marginTop: 8, padding: "14px 16px", borderRadius: 8,
                  background: colors.editor, color: colors.codeFg,
                  fontSize: 13, lineHeight: 1.5, overflowX: "auto", whiteSpace: "pre-wrap",
                }}>
                  {result.sql}
                </pre>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Small dashboard tile rendering a metric series as a bar chart, reusing the same
// QueryChart visualizer the Ask answers use (DRY — one chart implementation).
function DashboardCard({ title, data }) {
  const rows = (data || []).map((d) => [d.label, d.count]);
  return (
    <div style={{
      background: colors.surface,
      border: `1px solid ${colors.border}`,
      borderRadius: 10,
      padding: "18px 22px",
    }}>
      <div style={{ ...labelStyle, fontSize: 12, marginBottom: 16 }}>{title}</div>
      <QueryChart columns={["", "count"]} rows={rows} viz="bar" />
    </div>
  );
}
