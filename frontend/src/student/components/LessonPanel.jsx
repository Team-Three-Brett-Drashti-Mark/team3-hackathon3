import React from "react";
import { LESSON_INTRO, LESSON_BODY } from "../data/lessonContent";
import { colors, labelStyle } from "../styles/theme";

// Reference card showing the lesson content.
// Accepts a `style` prop so the parent's vertical drag handle can control height.
export default function LessonPanel({ style }) {
  return (
    <div style={{
      background: colors.surface,
      border: `1px solid ${colors.border}`,
      borderRadius: 8,
      display: "flex",
      flexDirection: "column",
      overflow: "hidden",
      ...style,
    }}>
      <div style={{
        padding: "11px 16px",
        borderBottom: `1px solid ${colors.border}`,
        display: "flex",
        alignItems: "center",
        gap: 8,
        flexShrink: 0,
      }}>
        <div style={{ width: 6, height: 6, borderRadius: "50%", background: colors.muted, flexShrink: 0 }} />
        <span style={labelStyle}>Lesson</span>
      </div>
      <pre style={{
        flex: 1,
        overflow: "auto",
        whiteSpace: "pre-wrap",
        lineHeight: 1.75,
        fontFamily: "ui-monospace, Consolas, monospace",
        color: colors.codeFg,
        margin: 0,
        padding: "12px 16px",
        fontSize: 12.5,
      }}>
        <span style={{ color: colors.text, fontWeight: 700 }}>{LESSON_INTRO}</span>{LESSON_BODY}
      </pre>
    </div>
  );
}
