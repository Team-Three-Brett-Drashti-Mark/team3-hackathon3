import { useState, useRef, useEffect } from "react";
import { sendChatMessage } from "../services/chatApi";

// Manages the AI tutor chat panel state for a single question session.
// sessionIdRef groups all turns for one question in backend logs without
// storing any user identity; it resets when the student moves to a new question.
export function useChat(currentQuestion) {
  const [prompt, setPrompt] = useState("");
  const [chat, setChat] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  const attemptRef = useRef(1);
  const sessionIdRef = useRef(crypto.randomUUID());
  const chatEndRef = useRef(null);

  // Auto-scroll to the latest message whenever the chat updates.
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat, isLoading]);

  // Wipes history and issues a fresh session ID so the backend treats
  // the next question as a completely new conversation.
  const reset = () => {
    setChat([]);
    attemptRef.current = 1;
    sessionIdRef.current = crypto.randomUUID();
  };

  const sendPrompt = async () => {
    if (!prompt.trim() || isLoading) return;

    const userMessage = prompt.trim();
    setPrompt("");
    setIsLoading(true);
    setChat((prev) => [...prev, { role: "user", text: userMessage }]);

    try {
      // Build history from the pre-setChat snapshot — React state is async,
      // so `chat` here still holds the turns before the new user message.
      // "hint" is the display role; the backend expects "assistant".
      const conversationHistory = chat.map((m) => ({
        role: m.role === "hint" ? "assistant" : m.role,
        content: m.text,
      }));

      const data = await sendChatMessage({
        userInput: userMessage,
        lessonContext: currentQuestion.text,
        attempt: attemptRef.current,
        sessionId: sessionIdRef.current,
        conversationHistory,
      });

      // Increment so the backend can progressively reveal more on repeated asks.
      if (data.intent === "answer_seeking" && attemptRef.current < 3) {
        attemptRef.current += 1;
      }

      setChat((prev) => [
        ...prev,
        { role: "hint", text: data.response_text, intent: data.intent },
      ]);
    } catch (error) {
      const message = error instanceof Error
        ? error.message
        : "Unknown chat error.";

      setChat((prev) => [
        ...prev,
        {
          role: "hint",
          text: `Pathwise chat failed: ${message}`,
          intent: "error",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return { prompt, setPrompt, chat, isLoading, sendPrompt, chatEndRef, reset };
}
