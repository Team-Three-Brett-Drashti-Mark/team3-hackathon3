import React, { useState } from "react";
import { colors, labelStyle } from "../styles/theme";

// Left-column AI tutor: message history, typing indicator, and prompt input bar.
export default function ChatPanel({ chat, isLoading, prompt, setPrompt, onSend, chatEndRef }) {
  const [hovered, setHovered] = useState(false);

  return (
    <div style={{
      background: colors.surface,
      border: `1px solid ${colors.border}`,
      borderRadius: 8,
      display: "flex",
      flexDirection: "column",
      overflow: "hidden",
      height: "100%",
    }}>
      {/* Panel header */}
      <div style={{
        padding: "11px 16px",
        borderBottom: `1px solid ${colors.border}`,
        display: "flex",
        alignItems: "center",
        gap: 8,
        flexShrink: 0,
      }}>
        <div style={{ width: 6, height: 6, borderRadius: "50%", background: colors.accent, flexShrink: 0 }} />
        <span style={labelStyle}>AI Tutor</span>
      </div>

      {/* Message list */}
      <div style={{ flex: 1, overflowY: "auto", padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>

        {/* Empty state */}
        {chat.length === 0 && !isLoading && (
          <div style={{
            flex: 1, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center",
            color: colors.muted, textAlign: "center", gap: 12, padding: "0 28px",
          }}>
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke={colors.border} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
            <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65 }}>
              Ask Pathwise anything about this lesson. It won't give you the answer, but it will help you think through it.
            </p>
          </div>
        )}

        {/* Messages — consecutive messages from the same role share one label */}
        {chat.map((msg, i) => {
          const prevMsg = i > 0 ? chat[i - 1] : null;
          const showLabel = !prevMsg || prevMsg.role !== msg.role;
          const isUser = msg.role === "user";
          const isError = msg.intent === "error";

          return (
            <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: isUser ? "flex-end" : "flex-start" }}>
              {showLabel && (
                <div style={{ ...labelStyle, color: isUser ? colors.accent : colors.muted, marginBottom: 5 }}>
                  {isUser ? "You" : "Pathwise"}
                </div>
              )}
              <div style={{
                maxWidth: "88%",
                padding: "9px 13px",
                borderRadius: isUser ? "8px 8px 2px 8px" : "8px 8px 8px 2px",
                background: isUser ? "rgba(236,192,88,0.1)" : colors.bg,
                border: `1px solid ${isUser ? "rgba(236,192,88,0.3)" : colors.border}`,
                fontSize: 13,
                lineHeight: 1.65,
                color: isError ? colors.errorFg : colors.text,
                whiteSpace: "pre-wrap",
              }}>
                {msg.text}
              </div>
            </div>
          );
        })}

        {/* Typing indicator while awaiting backend response */}
        {isLoading && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start" }}>
            <div style={{ ...labelStyle, color: colors.muted, marginBottom: 5 }}>Pathwise</div>
            <div className="thinking" style={{
              padding: "9px 13px",
              borderRadius: "8px 8px 8px 2px",
              background: colors.bg,
              border: `1px solid ${colors.border}`,
              fontSize: 13, color: colors.muted, fontStyle: "italic",
            }}>
              Thinking…
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Input bar */}
      <div style={{
        padding: "10px 12px",
        borderTop: `1px solid ${colors.border}`,
        display: "flex",
        gap: 8,
        flexShrink: 0,
      }}>
        <input
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !isLoading) onSend(); }}
          placeholder="Ask for a hint..."
          aria-label="Ask the AI tutor"
          style={{
            flex: 1,
            background: colors.bg,
            border: `1px solid ${colors.border}`,
            borderRadius: 6,
            color: colors.text,
            padding: "9px 13px",
            fontSize: 13,
            outline: "none",
            fontFamily: "Inter, system-ui, sans-serif",
          }}
        />
        <button
          onClick={onSend}
          disabled={isLoading || !prompt.trim()}
          aria-label="Send message"
          style={{
            background: hovered && !isLoading && prompt.trim() ? "#d4a948" : colors.accent,
            color: colors.accentText,
            border: "none",
            borderRadius: 6,
            width: 38,
            fontWeight: 700,
            fontSize: 15,
            cursor: isLoading || !prompt.trim() ? "not-allowed" : "pointer",
            opacity: isLoading || !prompt.trim() ? 0.45 : 1,
            transition: "background 0.15s, opacity 0.15s",
            flexShrink: 0,
          }}
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
        >
          →
        </button>
      </div>
    </div>
  );
}
