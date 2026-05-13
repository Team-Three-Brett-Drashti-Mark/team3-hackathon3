import React, { useState, useRef } from "react";

export default function App() {
  // ============================================================================
  // CONTENT
  // ============================================================================

  const APP_TITLE = "Pathwise — Strings";
  const PAGE_TITLE = "Strings";
  const PAGE_SUBTITLE = "Python Fundamentals · Unit 1";

  const LESSON_BOLD_PREFIX = "Strings in Python";

  const LESSON_BODY = `
Strings in Python are sequences of characters enclosed in single or double quotes.
They are immutable, meaning once created they cannot be changed in place — but
you can always create new strings from them.

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
len(word)      → 6
`;

  const QUESTIONS = [
    {
      unit: "Unit 1.0",
      text: 'Slice the first three characters from the string "cheese"',
      accepted: ['cheese[:3]', '"cheese"[:3]', "'cheese'[:3]"],
      hint:
        'Try square-bracket slice notation → string[start:end]\nExample: "hello"[0:2] gives "he"',
    },
    {
      unit: "Unit 1.1",
      text: 'Convert the string "hello" to uppercase.',
      accepted: ['"hello".upper()', "'hello'.upper()", "hello.upper()"],
      hint:
        "String objects have a built-in method that returns an uppercase copy.\nTry: your_string.upper()",
    },
    {
      unit: "Unit 1.2",
      text: 'Get the length of the string "python".',
      accepted: ['len("python")', "len('python')", "len(python)"],
      hint:
        "Python has a built-in function that counts items in any sequence.\nTry: len(your_string)",
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

  const [prompt, setPrompt] = useState("");
  const [chat, setChat] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const attemptRef = useRef(1); // tracks guardrail escalation per-session

  const currentQuestion = QUESTIONS[qIndex];

  // ============================================================================
  // HANDLERS
  // ============================================================================

  const submitAnswer = () => {
    if (!answer.trim()) return;

    const normalized = answer
      .replace(/\s/g, "")
      .toLowerCase()
      .replace(/['"]/g, "");

    const correct = currentQuestion.accepted.some((a) => {
      const cleaned = a
        .replace(/\s/g, "")
        .toLowerCase()
        .replace(/['"]/g, "");

      return (
        answer.replace(/\s/g, "") === a.replace(/\s/g, "") ||
        normalized === cleaned
      );
    });

    if (correct) {
      if (!completed.includes(qIndex)) {
        setCompleted([...completed, qIndex]);
      }

      setFeedback({
        type: "success",
        text: "✓ Correct! Nice work.",
      });

      setNextEnabled(true);
    } else {
      setFeedback({
        type: "error",
        text: "✗ Not quite — check your syntax and try again.",
      });
    }
  };

  const nextQuestion = () => {
    if (qIndex < QUESTIONS.length - 1) {
      setQIndex(qIndex + 1);
      resetQuestionState();
    } else {
      alert("Unit Complete! 🎉");
    }
  };

  const resetQuestionState = () => {
    setAnswer("");
    setFeedback(null);
    setNextEnabled(false);
    setChat([]);
    attemptRef.current = 1; // reset guardrail counter on new question
  };

  const jumpToQuestion = (index) => {
    setQIndex(index);
    resetQuestionState();
  };

  const sendPrompt = async () => {
    if (!prompt.trim() || isLoading) return;

    const userMessage = prompt.trim();
    setPrompt("");
    setIsLoading(true);

    // Optimistically add the user message to chat
    setChat((prev) => [...prev, { role: "user", text: userMessage }]);

    try {
      const res = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_input: userMessage,
          attempt: attemptRef.current,
        }),
      });

      const data = await res.json();

      // Escalate attempt counter if the student was seeking a direct answer
      if (data.intent === "answer_seeking" && attemptRef.current < 3) {
        attemptRef.current += 1;
      }

      setChat((prev) => [
        ...prev,
        { role: "hint", text: data.response_text, intent: data.intent },
      ]);
    } catch (err) {
      setChat((prev) => [
        ...prev,
        {
          role: "hint",
          text: "⚠️ Could not reach the Pathwise backend. Make sure the API server is running on port 8000.",
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

  const colors = {
    bg: "#0F1117",
    navbar: "#151A28",
    panel: "#1E2435",
    sidebar: "#161B27",
    border: "#2E3650",

    teal: "#00C9A7",
    tealHover: "#00A88A",

    amber: "#FFB627",
    blue: "#4C8BF5",

    text: "#E8ECF4",
    muted: "#6B7A99",
    code: "#A8D8B9",

    successBg: "#0D2B1E",
    successFg: "#34D399",

    errorBg: "#2B0D0D",
    errorFg: "#F87171",

    codeBg: "#141824",
  };

  // ============================================================================
  // UI
  // ============================================================================

  return (
    <div
      style={{
        background: colors.bg,
        minHeight: "100vh",
        color: colors.text,
        fontFamily: "Inter, sans-serif",
      }}
    >
      {/* NAVBAR */}
      <div
        style={{
          height: 72,
          background: colors.navbar,
          borderBottom: `2px solid ${colors.teal}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 24px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div
            style={{
              width: 14,
              height: 14,
              borderRadius: "50%",
              background: colors.teal,
            }}
          />

          <div>
            <h1
              style={{
                margin: 0,
                fontSize: 28,
                fontWeight: 700,
              }}
            >
              {PAGE_TITLE}
            </h1>

            <p
              style={{
                margin: 0,
                color: colors.muted,
                fontSize: 14,
              }}
            >
              {PAGE_SUBTITLE}
            </p>
          </div>
        </div>

        <div
          style={{
            background: colors.panel,
            border: `1px solid ${colors.border}`,
            padding: "8px 14px",
            borderRadius: 8,
            color: colors.teal,
            fontWeight: 700,
          }}
        >
          {QUESTIONS.length} Questions
        </div>
      </div>

      {/* MAIN LAYOUT */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1.2fr 1.5fr 0.8fr",
          gap: 16,
          padding: 16,
          height: "calc(100vh - 72px)",
        }}
      >
        {/* LEFT COLUMN */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 16,
          }}
        >
          {/* LESSON */}
          <div
            style={{
              background: colors.panel,
              border: `1px solid ${colors.border}`,
              borderRadius: 12,
              padding: 20,
              flex: 1,
              overflow: "auto",
            }}
          >
            <div
              style={{
                color: colors.teal,
                fontSize: 12,
                fontWeight: 700,
                marginBottom: 14,
                letterSpacing: 1,
              }}
            >
              📖 LESSON
            </div>

            <pre
              style={{
                whiteSpace: "pre-wrap",
                lineHeight: 1.7,
                fontFamily: "monospace",
                color: colors.code,
                margin: 0,
              }}
            >
              <span
                style={{
                  color: colors.text,
                  fontWeight: "bold",
                }}
              >
                {LESSON_BOLD_PREFIX}
              </span>
              {LESSON_BODY.replace(LESSON_BOLD_PREFIX, "")}
            </pre>
          </div>

          {/* AI TUTOR */}
          <div
            style={{
              background: colors.panel,
              border: `1px solid ${colors.border}`,
              borderRadius: 12,
              padding: 20,
              height: 320,
              display: "flex",
              flexDirection: "column",
            }}
          >
            <div
              style={{
                color: colors.amber,
                fontSize: 12,
                fontWeight: 700,
                marginBottom: 16,
                letterSpacing: 1,
              }}
            >
              🤖 AI TUTOR
            </div>

            <div
              style={{
                flex: 1,
                overflowY: "auto",
                marginBottom: 16,
              }}
            >
              {chat.map((msg, i) => (
                <div key={i} style={{ marginBottom: 16 }}>
                  {msg.role === "user" ? (
                    <div>
                      <div
                        style={{
                          color: colors.amber,
                          fontWeight: 700,
                          marginBottom: 4,
                        }}
                      >
                        You
                      </div>

                      <div>{msg.text}</div>
                    </div>
                  ) : (
                    <div>
                      <div
                        style={{
                          color: msg.intent === "error" ? colors.errorFg : colors.teal,
                          fontWeight: 700,
                          marginBottom: 4,
                        }}
                      >
                        Pathwise
                      </div>

                      <div
                        style={{
                          whiteSpace: "pre-wrap",
                          color: colors.code,
                          lineHeight: 1.6,
                        }}
                      >
                        {msg.text}
                      </div>
                    </div>
                  )}
                </div>
              ))}

              {/* Loading indicator */}
              {isLoading && (
                <div style={{ color: colors.muted, fontStyle: "italic", fontSize: 13 }}>
                  Pathwise is thinking…
                </div>
              )}
            </div>

            <div
              style={{
                display: "flex",
                gap: 10,
              }}
            >
              <input
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") sendPrompt();
                }}
                placeholder="Ask Pathwise for help..."
                style={{
                  flex: 1,
                  background: colors.codeBg,
                  border: `1px solid ${colors.border}`,
                  borderRadius: 8,
                  color: colors.text,
                  padding: 12,
                  outline: "none",
                }}
              />

              <button
                onClick={sendPrompt}
                style={{
                  background: colors.teal,
                  color: "#000",
                  border: "none",
                  borderRadius: 8,
                  padding: "0 18px",
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                ▶
              </button>
            </div>
          </div>
        </div>

        {/* CENTER COLUMN */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 16,
          }}
        >
          {/* QUESTION */}
          <div
            style={{
              background: colors.panel,
              border: `1px solid ${colors.border}`,
              borderRadius: 12,
              padding: 24,
            }}
          >
            <div
              style={{
                color: colors.blue,
                fontWeight: 700,
                marginBottom: 20,
              }}
            >
              Question {qIndex + 1}
            </div>

            <div
              style={{
                fontSize: 24,
                lineHeight: 1.5,
                textAlign: "center",
              }}
            >
              {currentQuestion.text}
            </div>
          </div>

          {/* ANSWER EDITOR */}
          <div
            style={{
              background: colors.codeBg,
              border: `1px solid ${colors.border}`,
              borderRadius: 12,
              flex: 1,
              display: "flex",
              flexDirection: "column",
            }}
          >
            {/* HEADER */}
            <div
              style={{
                height: 40,
                borderBottom: `1px solid ${colors.border}`,
                display: "flex",
                alignItems: "center",
                padding: "0 14px",
                gap: 8,
              }}
            >
              <div
                style={{
                  width: 12,
                  height: 12,
                  borderRadius: "50%",
                  background: "#FF5F57",
                }}
              />

              <div
                style={{
                  width: 12,
                  height: 12,
                  borderRadius: "50%",
                  background: "#FEBC2E",
                }}
              />

              <div
                style={{
                  width: 12,
                  height: 12,
                  borderRadius: "50%",
                  background: "#28C840",
                }}
              />

              <div
                style={{
                  marginLeft: 12,
                  color: colors.muted,
                  fontSize: 14,
                  fontFamily: "monospace",
                }}
              >
                answer.py
              </div>
            </div>

            {/* TEXTAREA */}
            <textarea
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              spellCheck={false}
              style={{
                flex: 1,
                background: colors.codeBg,
                border: "none",
                resize: "none",
                color: colors.code,
                padding: 20,
                fontFamily: "monospace",
                fontSize: 16,
                outline: "none",
              }}
            />

            {/* FEEDBACK */}
            {feedback && (
              <div
                style={{
                  padding: 14,
                  background:
                    feedback.type === "success"
                      ? colors.successBg
                      : colors.errorBg,

                  color:
                    feedback.type === "success"
                      ? colors.successFg
                      : colors.errorFg,

                  fontWeight: 700,
                  borderTop: `1px solid ${colors.border}`,
                }}
              >
                {feedback.text}
              </div>
            )}
          </div>

          {/* BUTTONS */}
          <div
            style={{
              display: "flex",
              gap: 12,
            }}
          >
            <button
              onClick={submitAnswer}
              style={{
                background: colors.teal,
                color: "#000",
                border: "none",
                borderRadius: 8,
                padding: "14px 22px",
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              Submit Answer
            </button>

            <button
              onClick={nextQuestion}
              disabled={!nextEnabled}
              style={{
                background: nextEnabled
                  ? colors.border
                  : "#1A1F2B",

                color: nextEnabled
                  ? colors.text
                  : "#3A4460",

                border: "none",
                borderRadius: 8,
                padding: "14px 22px",
                fontWeight: 700,
                cursor: nextEnabled ? "pointer" : "not-allowed",
              }}
            >
              Next →
            </button>
          </div>
        </div>

        {/* RIGHT SIDEBAR */}
        <div>
          <div
            style={{
              background: colors.sidebar,
              border: `1px solid ${colors.border}`,
              borderRadius: 12,
              height: "100%",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                height: 4,
                background: colors.amber,
              }}
            />

            <div
              style={{
                padding: 20,
                borderBottom: `1px solid ${colors.border}`,
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div
                style={{
                  fontWeight: 700,
                }}
              >
                Progress
              </div>

              <div
                style={{
                  background: colors.panel,
                  padding: "6px 10px",
                  borderRadius: 8,
                  color: colors.teal,
                  fontWeight: 700,
                  fontSize: 13,
                }}
              >
                {completed.length} / {QUESTIONS.length}
              </div>
            </div>

            {QUESTIONS.map((q, index) => {
              const active = index === qIndex;
              const done = completed.includes(index);

              return (
                <div
                  key={index}
                  onClick={() => jumpToQuestion(index)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    padding: "16px 20px",
                    cursor: "pointer",

                    background: active
                      ? "#1A2540"
                      : "transparent",
                  }}
                >
                  <div
                    style={{
                      color: active
                        ? colors.amber
                        : done
                        ? "#34D399"
                        : "#4A5568",

                      fontWeight: 700,
                    }}
                  >
                    {active ? "▶" : done ? "✓" : "○"}
                  </div>

                  <div
                    style={{
                      color: active
                        ? colors.amber
                        : done
                        ? "#34D399"
                        : "#6B7A99",

                      fontWeight: active ? 700 : 400,
                    }}
                  >
                    {q.unit}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}