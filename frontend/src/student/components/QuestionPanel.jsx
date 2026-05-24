import React, { useState } from "react";
import { colors, labelStyle } from "../styles/theme";

// Question text, compact code editor, inline feedback, and Submit/Next buttons.
// The editor is intentionally small so the lesson reference above stays fully visible.
export default function QuestionPanel({
  question, qIndex, total,
  answer, setAnswer,
  feedback, nextEnabled,
  onSubmit, onNext,
}) {
  const [hovered, setHovered] = useState(null);

  return (
    <>
      {/* Question prompt */}
      <div style={{
        background: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: 8,
        padding: "14px 16px",
        flexShrink: 0,
        boxShadow: `inset 3px 0 0 ${colors.accent}`,
      }}>
        <div style={{ ...labelStyle, color: colors.accent, marginBottom: 8 }}>
          Question {qIndex + 1} of {total}
        </div>
        <div style={{ fontSize: 17, lineHeight: 1.55, color: colors.text, fontWeight: 500 }}>
          {question.text}
        </div>
      </div>

      {/* Code editor */}
      <div style={{
        background: colors.editor,
        border: `1px solid ${colors.border}`,
        borderRadius: 8,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        flexShrink: 0,
      }}>
        {/* Decorative macOS-style window chrome */}
        <div style={{
          height: 36,
          background: colors.surface,
          borderBottom: `1px solid ${colors.border}`,
          display: "flex",
          alignItems: "center",
          padding: "0 12px",
          gap: 6,
          flexShrink: 0,
        }}>
          <div style={{ width: 11, height: 11, borderRadius: "50%", background: "#FF5F57" }} />
          <div style={{ width: 11, height: 11, borderRadius: "50%", background: "#FEBC2E" }} />
          <div style={{ width: 11, height: 11, borderRadius: "50%", background: "#28C840" }} />
          <div style={{ marginLeft: 10, color: colors.muted, fontSize: 12, fontFamily: "ui-monospace, Consolas, monospace" }}>
            answer.py
          </div>
          <div style={{ marginLeft: "auto", color: colors.muted, fontSize: 11, letterSpacing: "0.3px" }}>
            ⌘ Enter to submit
          </div>
        </div>

        {/* Fixed height keeps the editor compact so the lesson stays visible above */}
        <textarea
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) onSubmit(); }}
          spellCheck={false}
          placeholder="# type your answer here"
          aria-label="Code answer"
          style={{
            height: 80,
            background: colors.editor,
            border: "none",
            resize: "none",
            color: colors.codeFg,
            padding: "10px 16px",
            fontFamily: "ui-monospace, Consolas, monospace",
            fontSize: 14,
            lineHeight: 1.65,
            outline: "none",
          }}
        />

        {feedback && (
          <div style={{
            padding: "10px 16px",
            background: feedback.type === "success" ? colors.successBg : colors.errorBg,
            color: feedback.type === "success" ? colors.successFg : colors.errorFg,
            fontWeight: 600,
            fontSize: 13,
            borderTop: `1px solid ${colors.border}`,
            flexShrink: 0,
          }}>
            {feedback.text}
          </div>
        )}
      </div>

      {/* Action buttons */}
      <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
        <button
          onClick={onSubmit}
          style={{
            flex: 2,
            background: hovered === "submit" ? "#d4a948" : colors.accent,
            color: colors.accentText,
            border: "none",
            borderRadius: 6,
            padding: "12px 0",
            fontWeight: 700,
            fontSize: 14,
            cursor: "pointer",
            letterSpacing: "0.3px",
            transition: "background 0.15s",
          }}
          onMouseEnter={() => setHovered("submit")}
          onMouseLeave={() => setHovered(null)}
        >
          Submit Answer
        </button>
        <button
          onClick={onNext}
          disabled={!nextEnabled}
          style={{
            flex: 1,
            background: nextEnabled
              ? hovered === "next" ? "#2a2520" : colors.text
              : "transparent",
            color: nextEnabled ? colors.navText : colors.muted,
            border: `1px solid ${nextEnabled ? colors.text : colors.border}`,
            borderRadius: 6,
            padding: "12px 0",
            fontWeight: 700,
            fontSize: 14,
            cursor: nextEnabled ? "pointer" : "not-allowed",
            letterSpacing: "0.3px",
            transition: "all 0.15s",
          }}
          onMouseEnter={() => nextEnabled && setHovered("next")}
          onMouseLeave={() => setHovered(null)}
        >
          Next →
        </button>
      </div>
    </>
  );
}
