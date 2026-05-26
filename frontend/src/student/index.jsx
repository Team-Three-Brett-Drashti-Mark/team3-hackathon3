import React, { useState, useRef, useEffect } from "react";
import { QUESTIONS, PAGE_SUBTITLE } from "./data/lessonContent";
import { useQuiz } from "./hooks/useQuiz";
import { useChat } from "./hooks/useChat";
import { colors } from "./styles/theme";
import Navbar from "./components/Navbar";
import ChatPanel from "./components/ChatPanel";
import ProgressStrip from "./components/ProgressStrip";
import LessonPanel from "./components/LessonPanel";
import QuestionPanel from "./components/QuestionPanel";
import UnitComplete from "./components/UnitComplete";

// Root of the student view. Composes hooks + components and owns the two
// transition handlers that need to coordinate quiz and chat state together.
export default function StudentApp() {
  const quiz = useQuiz();
  const chatState = useChat(quiz.currentQuestion);

  // ── Resizable left/right column split ──────────────────────────────────────
  // Stored as a percentage so it scales with viewport width changes.
  const [leftPct, setLeftPct] = useState(38);
  const hDragRef = useRef(false);

  // ── Resizable lesson panel height within the right column ──────────────────
  const [lessonHeight, setLessonHeight] = useState(260);
  // Track the drag start position and panel height so we can compute delta
  // instead of doing fragile absolute coordinate math.
  const vDragRef = useRef({ dragging: false, startY: 0, startH: 0 });

  // Single effect handles both drag handles to avoid duplicate event listeners.
  useEffect(() => {
    const onMove = (e) => {
      if (hDragRef.current) {
        const pct = (e.clientX / window.innerWidth) * 100;
        // Clamp: chat panel stays between 20% and 65% wide.
        setLeftPct(Math.min(Math.max(pct, 20), 65));
      }
      if (vDragRef.current.dragging) {
        const delta = e.clientY - vDragRef.current.startY;
        const newH = vDragRef.current.startH + delta;
        // Clamp: lesson panel stays between 120px and 420px tall.
        setLessonHeight(Math.min(Math.max(newH, 120), 420));
      }
    };
    const onUp = () => {
      hDragRef.current = false;
      vDragRef.current.dragging = false;
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  // ── Question transition handlers ───────────────────────────────────────────
  // These coordinate both hooks; neither hook knows about the other.

  const handleNext = () => {
    // Don't wipe chat when finishing the last question — the student may still
    // want to reference the conversation on the completion screen.
    if (quiz.qIndex < QUESTIONS.length - 1) chatState.reset();
    quiz.goNext();
  };

  const handleJump = (index) => {
    chatState.reset();
    quiz.goToQuestion(index);
  };

  const handleRestart = () => {
    chatState.reset();
    quiz.restart();
  };

  return (
    <div style={{
      background: colors.bg,
      minHeight: "100vh",
      color: colors.text,
      fontFamily: "Inter, system-ui, sans-serif",
    }}>
      <Navbar
        pageSubtitle={PAGE_SUBTITLE}
        completedCount={quiz.completed.length}
        totalCount={QUESTIONS.length}
      />

      {/* Two-column layout with a draggable vertical divider */}
      <div style={{
        display: "grid",
        gridTemplateColumns: `${leftPct}% 8px 1fr`,
        padding: 12,
        gap: 0,
        height: "calc(100vh - 52px)",
        boxSizing: "border-box",
      }}>

        {/* Left column: AI tutor chat */}
        <ChatPanel
          chat={chatState.chat}
          isLoading={chatState.isLoading}
          prompt={chatState.prompt}
          setPrompt={chatState.setPrompt}
          onSend={chatState.sendPrompt}
          chatEndRef={chatState.chatEndRef}
        />

        {/* Horizontal drag handle — separates chat from content */}
        <div
          onMouseDown={() => { hDragRef.current = true; }}
          title="Drag to resize columns"
          style={{
            cursor: "col-resize",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            userSelect: "none",
          }}
        >
          <div style={{
            width: 2,
            height: "80%",
            background: colors.border,
            borderRadius: 2,
          }} />
        </div>

        {/* Right column: progress strip, lesson reference, question/answer */}
        <div style={{
          display: "flex",
          flexDirection: "column",
          gap: 12,
          paddingLeft: 4,
          overflowY: "auto",
        }}>
          <ProgressStrip
            questions={QUESTIONS}
            qIndex={quiz.qIndex}
            completed={quiz.completed}
            unitComplete={quiz.unitComplete}
            onJump={handleJump}
          />

          {/* Lesson reference with user-adjustable height */}
          <LessonPanel style={{ flex: `0 0 ${lessonHeight}px` }} />

          {/* Vertical drag handle — separates lesson from question panel */}
          <div
            onMouseDown={(e) => {
              vDragRef.current = { dragging: true, startY: e.clientY, startH: lessonHeight };
            }}
            title="Drag to resize lesson panel"
            style={{
              height: 10,
              cursor: "row-resize",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
              marginTop: -8,
              marginBottom: -4,
            }}
          >
            <div style={{
              width: "30%",
              height: 2,
              background: colors.border,
              borderRadius: 2,
            }} />
          </div>

          {quiz.unitComplete ? (
            <UnitComplete total={QUESTIONS.length} onRestart={handleRestart} />
          ) : (
            <QuestionPanel
              question={quiz.currentQuestion}
              qIndex={quiz.qIndex}
              total={QUESTIONS.length}
              answer={quiz.answer}
              setAnswer={quiz.setAnswer}
              feedback={quiz.feedback}
              nextEnabled={quiz.nextEnabled}
              onSubmit={quiz.submitAnswer}
              onNext={handleNext}
            />
          )}
        </div>

      </div>
    </div>
  );
}
