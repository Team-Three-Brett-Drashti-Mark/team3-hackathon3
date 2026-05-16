import React, { useState, useRef, useEffect } from "react";
import "./App.css";

export default function App() {
  // ============================================================================
  // CONTENT
  // ============================================================================

  const PAGE_SUBTITLE = "Python Fundamentals · Unit 1";

  const LESSON_INTRO = "Strings in Python";
  const LESSON_BODY = ` are sequences of characters enclosed in single or double
quotes. They are immutable — once created they cannot be changed in place,
but you can always create new strings from them.

── Slicing ──────────────────────
s[start : end]   extract a portion
s[0:3]           first three chars
s[-3:]           last three chars
s[::2]           every other char

── Common Methods ───────────────
.upper()   .lower()   .strip()
.split()   .join()    .replace()
.find()    .count()   .startswith()

── Examples ─────────────────────
word = "cheese"

word[:3]       → "che"
word.upper()   → "CHEESE"
len(word)      → 6`;

  const QUESTIONS = [
    {
      unit: "Unit 1.0",
      text: 'Slice the first three characters from the string "cheese"',
      accepted: ['cheese[:3]', '"cheese"[:3]', "'cheese'[:3]"],
      hint: 'Try square-bracket slice notation → string[start:end]\nExample: "hello"[0:2] gives "he"',
    },
    {
      unit: "Unit 1.1",
      text: 'Convert the string "hello" to uppercase.',
      accepted: ['"hello".upper()', "'hello'.upper()", "hello.upper()"],
      hint: "String objects have a built-in method that returns an uppercase copy.\nTry: your_string.upper()",
    },
    {
      unit: "Unit 1.2",
      text: 'Get the length of the string "python".',
      accepted: ['len("python")', "len('python')", "len(python)"],
      hint: "Python has a built-in function that counts items in any sequence.\nTry: len(your_string)",
    },
  ];

  // ============================================================================
  // STATE
  // ============================================================================

  const [qIndex, setQIndex] = useState(0);
  const [completed, setCompleted] = useState([]);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState(null);
  const [nextEnabled, setNextEnabled] = useState(false);
  const [unitComplete, setUnitComplete] = useState(false);

  const [prompt, setPrompt] = useState("");
  const [chat, setChat] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hovered, setHovered] = useState(null);

  const attemptRef = useRef(1);
  const chatEndRef = useRef(null);

  const currentQuestion = QUESTIONS[qIndex];

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat, isLoading]);

  // ============================================================================
  // HANDLERS
  // ============================================================================

  const submitAnswer = () => {
    if (!answer.trim()) return;

    const normalized = answer.replace(/\s/g, "").toLowerCase().replace(/['"]/g, "");

    const correct = currentQuestion.accepted.some((a) => {
      const cleaned = a.replace(/\s/g, "").toLowerCase().replace(/['"]/g, "");
      return (
        answer.replace(/\s/g, "") === a.replace(/\s/g, "") ||
        normalized === cleaned
      );
    });

    if (correct) {
      if (!completed.includes(qIndex)) setCompleted((prev) => [...prev, qIndex]);
      setFeedback({ type: "success", text: "Correct — well done." });
      setNextEnabled(true);
    } else {
      setFeedback({ type: "error", text: "Not quite — check your syntax and try again." });
    }
  };

  const nextQuestion = () => {
    if (qIndex < QUESTIONS.length - 1) {
      setQIndex(qIndex + 1);
      resetQuestionState();
    } else {
      setUnitComplete(true);
    }
  };

  const resetQuestionState = () => {
    setAnswer("");
    setFeedback(null);
    setNextEnabled(false);
    setChat([]);
    attemptRef.current = 1;
  };

  const jumpToQuestion = (index) => {
    setUnitComplete(false);
    setQIndex(index);
    resetQuestionState();
  };

  const sendPrompt = async () => {
    if (!prompt.trim() || isLoading) return;

    const userMessage = prompt.trim();
    setPrompt("");
    setIsLoading(true);
    setChat((prev) => [...prev, { role: "user", text: userMessage }]);

    try {
      const res = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_input: userMessage, attempt: attemptRef.current }),
      });

      const data = await res.json();

      if (data.intent === "answer_seeking" && attemptRef.current < 3) {
        attemptRef.current += 1;
      }

      setChat((prev) => [
        ...prev,
        { role: "hint", text: data.response_text, intent: data.intent },
      ]);
    } catch {
      setChat((prev) => [
        ...prev,
        {
          role: "hint",
          text: "Could not reach the Pathwise backend. Make sure the API server is running on port 8000.",
          intent: "error",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // ============================================================================
  // STYLES
  // ============================================================================

  const c = {
    bg:          "#f3f1e2",
    surface:     "#fcf8ea",
    editor:      "#e8e4d4",
    nav:         "#1e1c18",
    navText:     "#fcf8ea",
    accent:      "#ecc058",
    accentText:  "#1e1c18",
    text:        "#1e1c18",
    muted:       "#888888",
    border:      "#d5d1be",
    codeFg:      "#3d5c35",
    successBg:   "#edf7f1",
    successFg:   "#2d7a4e",
    errorBg:     "#fdecea",
    errorFg:     "#b03a2e",
  };

  const labelStyle = {
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: "1.5px",
    textTransform: "uppercase",
    color: c.muted,
  };

  // ============================================================================
  // UI
  // ============================================================================

  return (
    <div style={{ background: c.bg, minHeight: "100vh", color: c.text, fontFamily: "Inter, system-ui, sans-serif" }}>

      {/* ── NAVBAR ── */}
      <div style={{
        height: 52,
        background: c.nav,
        borderBottom: `2px solid ${c.accent}`,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 20px",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{
            width: 28, height: 28, borderRadius: 6,
            background: c.accent,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 13, fontWeight: 900, color: c.nav, flexShrink: 0,
          }}>
            P
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
            <span style={{ color: c.navText, fontWeight: 700, fontSize: 15 }}>Pathwise</span>
            <span style={{ color: c.muted, fontSize: 13 }}>·</span>
            <span style={{ color: c.muted, fontSize: 13 }}>{PAGE_SUBTITLE}</span>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ ...labelStyle, color: c.muted }}>Progress</span>
          <span style={{
            fontSize: 13, fontWeight: 700, color: c.accent,
            background: "rgba(236,192,88,0.1)",
            border: "1px solid rgba(236,192,88,0.25)",
            padding: "3px 10px", borderRadius: 20,
          }}>
            {completed.length} / {QUESTIONS.length}
          </span>
        </div>
      </div>

      {/* ── MAIN LAYOUT ── */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "38% 1fr",
        gap: 12,
        padding: 12,
        height: "calc(100vh - 52px)",
        boxSizing: "border-box",
      }}>

        {/* ── LEFT: AI TUTOR ── */}
        <div style={{
          background: c.surface,
          border: `1px solid ${c.border}`,
          borderRadius: 8,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}>
          <div style={{
            padding: "11px 16px",
            borderBottom: `1px solid ${c.border}`,
            display: "flex",
            alignItems: "center",
            gap: 8,
            flexShrink: 0,
          }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: c.accent, flexShrink: 0 }} />
            <span style={labelStyle}>AI Tutor</span>
          </div>

          {/* Chat messages */}
          <div style={{ flex: 1, overflowY: "auto", padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>

            {/* Empty state */}
            {chat.length === 0 && !isLoading && (
              <div style={{
                flex: 1, display: "flex", flexDirection: "column",
                alignItems: "center", justifyContent: "center",
                color: c.muted, textAlign: "center", gap: 12, padding: "0 28px",
              }}>
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke={c.border} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
                <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65 }}>
                  Ask Pathwise anything about this lesson. It won't give you the answer, but it will help you think through it.
                </p>
              </div>
            )}

            {/* Messages with sender grouping */}
            {chat.map((msg, i) => {
              const prevMsg = i > 0 ? chat[i - 1] : null;
              const showLabel = !prevMsg || prevMsg.role !== msg.role;
              const isUser = msg.role === "user";
              const isError = msg.intent === "error";

              return (
                <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: isUser ? "flex-end" : "flex-start" }}>
                  {showLabel && (
                    <div style={{
                      ...labelStyle,
                      color: isUser ? c.accent : c.muted,
                      marginBottom: 5,
                    }}>
                      {isUser ? "You" : "Pathwise"}
                    </div>
                  )}
                  <div style={{
                    maxWidth: "88%",
                    padding: "9px 13px",
                    borderRadius: isUser ? "8px 8px 2px 8px" : "8px 8px 8px 2px",
                    background: isUser ? "rgba(236,192,88,0.1)" : c.bg,
                    border: `1px solid ${isUser ? "rgba(236,192,88,0.3)" : c.border}`,
                    fontSize: 13,
                    lineHeight: 1.65,
                    color: isError ? c.errorFg : c.text,
                    whiteSpace: "pre-wrap",
                  }}>
                    {msg.text}
                  </div>
                </div>
              );
            })}

            {/* Typing indicator */}
            {isLoading && (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start" }}>
                <div style={{ ...labelStyle, color: c.muted, marginBottom: 5 }}>Pathwise</div>
                <div className="thinking" style={{
                  padding: "9px 13px",
                  borderRadius: "8px 8px 8px 2px",
                  background: c.bg,
                  border: `1px solid ${c.border}`,
                  fontSize: 13, color: c.muted, fontStyle: "italic",
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
            borderTop: `1px solid ${c.border}`,
            display: "flex",
            gap: 8,
            flexShrink: 0,
          }}>
            <input
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !isLoading) sendPrompt(); }}
              placeholder="Ask for a hint..."
              aria-label="Ask the AI tutor"
              style={{
                flex: 1,
                background: c.bg,
                border: `1px solid ${c.border}`,
                borderRadius: 6,
                color: c.text,
                padding: "9px 13px",
                fontSize: 13,
                outline: "none",
                fontFamily: "Inter, system-ui, sans-serif",
              }}
            />
            <button
              onClick={sendPrompt}
              disabled={isLoading || !prompt.trim()}
              aria-label="Send message"
              style={{
                background: hovered === "send" && !isLoading && prompt.trim() ? "#d4a948" : c.accent,
                color: c.accentText,
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
              onMouseEnter={() => setHovered("send")}
              onMouseLeave={() => setHovered(null)}
            >
              →
            </button>
          </div>
        </div>

        {/* ── RIGHT COLUMN ── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

          {/* PROGRESS STRIP */}
          <div style={{
            background: c.surface,
            border: `1px solid ${c.border}`,
            borderRadius: 8,
            padding: "10px 16px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexShrink: 0,
          }}>
            <div style={{ display: "flex", gap: 6 }}>
              {QUESTIONS.map((q, index) => {
                const active = index === qIndex && !unitComplete;
                const done = completed.includes(index);
                return (
                  <button
                    key={index}
                    onClick={() => jumpToQuestion(index)}
                    style={{
                      padding: "4px 14px",
                      borderRadius: 20,
                      border: `1px solid ${active ? c.accent : done ? c.successFg : c.border}`,
                      background: active ? c.accent : done ? c.successBg : "transparent",
                      color: active ? c.accentText : done ? c.successFg : c.muted,
                      fontWeight: 700,
                      fontSize: 12,
                      cursor: "pointer",
                      letterSpacing: "0.3px",
                      transition: "all 0.15s",
                    }}
                  >
                    {done ? `✓ ${q.unit}` : q.unit}
                  </button>
                );
              })}
            </div>
            <span style={{ ...labelStyle, letterSpacing: "0.5px" }}>
              {completed.length} of {QUESTIONS.length} complete
            </span>
          </div>

          {/* LESSON */}
          <div style={{
            background: c.surface,
            border: `1px solid ${c.border}`,
            borderRadius: 8,
            display: "flex",
            flexDirection: "column",
            flex: "0 0 176px",
            overflow: "hidden",
          }}>
            <div style={{
              padding: "11px 16px",
              borderBottom: `1px solid ${c.border}`,
              display: "flex",
              alignItems: "center",
              gap: 8,
              flexShrink: 0,
            }}>
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: c.muted, flexShrink: 0 }} />
              <span style={labelStyle}>Lesson</span>
            </div>
            <pre style={{
              flex: 1,
              overflow: "auto",
              whiteSpace: "pre-wrap",
              lineHeight: 1.75,
              fontFamily: "ui-monospace, Consolas, monospace",
              color: c.codeFg,
              margin: 0,
              padding: "12px 16px",
              fontSize: 12.5,
            }}>
              <span style={{ color: c.text, fontWeight: 700 }}>{LESSON_INTRO}</span>{LESSON_BODY}
            </pre>
          </div>

          {/* QUESTION OR COMPLETION */}
          {unitComplete ? (
            <div style={{
              background: c.surface,
              border: `1px solid ${c.border}`,
              borderRadius: 8,
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 16,
              padding: 32,
              textAlign: "center",
            }}>
              <div style={{
                width: 48, height: 48, borderRadius: "50%",
                background: c.successBg,
                border: `2px solid ${c.successFg}`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 22, color: c.successFg, fontWeight: 700,
              }}>
                {"✓"}
              </div>
              <div>
                <div style={{ fontSize: 20, fontWeight: 700, color: c.text, marginBottom: 8 }}>Unit Complete</div>
                <div style={{ fontSize: 14, color: c.muted, lineHeight: 1.6 }}>
                  You answered all {QUESTIONS.length} questions correctly.
                </div>
              </div>
              <button
                onClick={() => { setCompleted([]); jumpToQuestion(0); }}
                style={{
                  background: hovered === "restart" ? "#d4a948" : c.accent,
                  color: c.accentText,
                  border: "none",
                  borderRadius: 6,
                  padding: "10px 24px",
                  fontWeight: 700,
                  fontSize: 14,
                  cursor: "pointer",
                  transition: "background 0.15s",
                }}
                onMouseEnter={() => setHovered("restart")}
                onMouseLeave={() => setHovered(null)}
              >
                Start Over
              </button>
            </div>
          ) : (
            <>
              {/* QUESTION */}
              <div style={{
                background: c.surface,
                border: `1px solid ${c.border}`,
                borderRadius: 8,
                padding: "14px 16px",
                flexShrink: 0,
                boxShadow: `inset 3px 0 0 ${c.accent}`,
              }}>
                <div style={{ ...labelStyle, color: c.accent, marginBottom: 8 }}>
                  Question {qIndex + 1} of {QUESTIONS.length}
                </div>
                <div style={{ fontSize: 17, lineHeight: 1.55, color: c.text, fontWeight: 500 }}>
                  {currentQuestion.text}
                </div>
              </div>

              {/* CODE EDITOR */}
              <div style={{
                background: c.editor,
                border: `1px solid ${c.border}`,
                borderRadius: 8,
                flex: 1,
                display: "flex",
                flexDirection: "column",
                overflow: "hidden",
                minHeight: 140,
              }}>
                {/* Window chrome */}
                <div style={{
                  height: 36,
                  background: c.surface,
                  borderBottom: `1px solid ${c.border}`,
                  display: "flex",
                  alignItems: "center",
                  padding: "0 12px",
                  gap: 6,
                  flexShrink: 0,
                }}>
                  <div style={{ width: 11, height: 11, borderRadius: "50%", background: "#FF5F57" }} />
                  <div style={{ width: 11, height: 11, borderRadius: "50%", background: "#FEBC2E" }} />
                  <div style={{ width: 11, height: 11, borderRadius: "50%", background: "#28C840" }} />
                  <div style={{ marginLeft: 10, color: c.muted, fontSize: 12, fontFamily: "ui-monospace, Consolas, monospace" }}>
                    answer.py
                  </div>
                  <div style={{ marginLeft: "auto", color: c.muted, fontSize: 11, letterSpacing: "0.3px" }}>
                    ⌘ Enter to submit
                  </div>
                </div>

                <textarea
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submitAnswer(); }}
                  spellCheck={false}
                  placeholder="# type your answer here"
                  aria-label="Code answer"
                  style={{
                    flex: 1,
                    background: c.editor,
                    border: "none",
                    resize: "none",
                    color: c.codeFg,
                    padding: "14px 16px",
                    fontFamily: "ui-monospace, Consolas, monospace",
                    fontSize: 14,
                    lineHeight: 1.65,
                    outline: "none",
                  }}
                />

                {feedback && (
                  <div style={{
                    padding: "10px 16px",
                    background: feedback.type === "success" ? c.successBg : c.errorBg,
                    color: feedback.type === "success" ? c.successFg : c.errorFg,
                    fontWeight: 600,
                    fontSize: 13,
                    borderTop: `1px solid ${c.border}`,
                    flexShrink: 0,
                  }}>
                    {feedback.text}
                  </div>
                )}
              </div>

              {/* BUTTONS */}
              <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
                <button
                  onClick={submitAnswer}
                  style={{
                    flex: 2,
                    background: hovered === "submit" ? "#d4a948" : c.accent,
                    color: c.accentText,
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
                  onClick={nextQuestion}
                  disabled={!nextEnabled}
                  style={{
                    flex: 1,
                    background: nextEnabled
                      ? hovered === "next" ? "#2a2520" : c.text
                      : "transparent",
                    color: nextEnabled ? c.navText : c.muted,
                    border: `1px solid ${nextEnabled ? c.text : c.border}`,
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
          )}

        </div>
      </div>
    </div>
  );
}
