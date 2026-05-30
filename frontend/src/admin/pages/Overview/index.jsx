import React, { useState } from "react";
import { colors, labelStyle } from "../../../student/styles/theme";
import { useOverviewMetrics } from "../../hooks/useOverviewMetrics";
import StatCard from "./StatCard";
import DailyUsageChart from "./DailyUsageChart";
import HourlyActivityChart from "./HourlyActivityChart";
import IntentBreakdownChart from "./IntentBreakdownChart";

// Overview dashboard: usage stats, struggling-session count, and charts.
export default function OverviewPage() {
  const [refreshKey, setRefreshKey] = useState(0);
  const { data, loading, error } = useOverviewMetrics(refreshKey);

  return (
    <div style={{ padding: "28px 32px", maxWidth: 860 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 24 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: colors.text }}>Overview</h1>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: colors.muted }}>Past 10 days</p>
        </div>
        <button
          onClick={() => setRefreshKey(Date.now())}
          style={{
            background: "transparent",
            border: `1px solid ${colors.border}`,
            borderRadius: 6,
            padding: "6px 14px",
            fontSize: 12,
            color: colors.muted,
            cursor: "pointer",
          }}
        >
          ↻ Refresh
        </button>
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

      {/* Stat cards */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 28 }}>
        <StatCard
          label="Questions today"
          value={data?.total_today ?? 0}
          loading={loading}
        />
        <StatCard
          label="Total questions asked"
          value={data?.total_week ?? 0}
          loading={loading}
        />
        {/* Highlighted when any sessions hit the hard block */}
        <StatCard
          label="Struggling sessions"
          value={data?.behind_count ?? 0}
          loading={loading}
          highlight={(data?.behind_count ?? 0) > 0}
        />
      </div>

      {/* Daily usage chart */}
      <div style={{
        background: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: 8,
        padding: "16px 20px",
        marginBottom: 20,
      }}>
        <div style={{ ...labelStyle, marginBottom: 14 }}>Daily questions asked</div>
        {/* The backend view can return an arbitrary history; cap to the most
            recent 10 days so the chart matches the "Past 10 days" header and
            stays readable. daily is sorted ascending, so slice(-10) is newest. */}
        <DailyUsageChart data={(data?.daily ?? []).slice(-10)} />
      </div>

      {/* Two-column row: hourly activity + intent breakdown */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div style={{
          background: colors.surface,
          border: `1px solid ${colors.border}`,
          borderRadius: 8,
          padding: "16px 20px",
        }}>
          <div style={{ ...labelStyle, marginBottom: 14 }}>Activity by hour of day</div>
          <HourlyActivityChart data={data?.hourly_activity ?? []} />
        </div>

        <div style={{
          background: colors.surface,
          border: `1px solid ${colors.border}`,
          borderRadius: 8,
          padding: "16px 20px",
        }}>
          <div style={{ ...labelStyle, marginBottom: 14 }}>Intent breakdown</div>
          <IntentBreakdownChart data={data?.intent_breakdown ?? []} />
        </div>
      </div>
    </div>
  );
}
