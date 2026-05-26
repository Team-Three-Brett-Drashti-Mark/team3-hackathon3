import { useState } from "react";
import { QUESTIONS } from "../data/lessonContent";

// Manages all question-progression and answer-validation state.
// Chat state lives separately in useChat so the two can reset independently
// when the student navigates between questions.
export function useQuiz() {
  const [qIndex, setQIndex] = useState(0);
  const [completed, setCompleted] = useState([]);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState(null);
  const [nextEnabled, setNextEnabled] = useState(false);
  const [unitComplete, setUnitComplete] = useState(false);

  const currentQuestion = QUESTIONS[qIndex];

  // Clears per-question UI state without touching progress or chat.
  const resetQuestion = () => {
    setAnswer("");
    setFeedback(null);
    setNextEnabled(false);
  };

  const submitAnswer = () => {
    if (!answer.trim()) return;

    // Normalize by stripping whitespace and quotes so minor formatting
    // differences don't mark a correct answer wrong.
    const normalized = answer.replace(/\s/g, "").toLowerCase().replace(/['"]/g, "");
    const correct = currentQuestion.accepted.some((a) => {
      const cleaned = a.replace(/\s/g, "").toLowerCase().replace(/['"]/g, "");
      return (
        answer.replace(/\s/g, "") === a.replace(/\s/g, "") || normalized === cleaned
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

  // Advances to the next question or marks the unit complete on the last one.
  const goNext = () => {
    if (qIndex < QUESTIONS.length - 1) {
      setQIndex(qIndex + 1);
      resetQuestion();
    } else {
      setUnitComplete(true);
    }
  };

  const goToQuestion = (index) => {
    setUnitComplete(false);
    setQIndex(index);
    resetQuestion();
  };

  const restart = () => {
    setCompleted([]);
    setUnitComplete(false);
    setQIndex(0);
    resetQuestion();
  };

  return {
    qIndex,
    completed,
    answer,
    setAnswer,
    feedback,
    nextEnabled,
    unitComplete,
    currentQuestion,
    submitAnswer,
    goNext,
    goToQuestion,
    restart,
  };
}
