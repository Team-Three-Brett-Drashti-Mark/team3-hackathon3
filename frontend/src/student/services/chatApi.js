// Sends one chat turn to the Pathwise backend and returns parsed JSON.
// Throws on network failure — callers must handle errors.
export async function sendChatMessage({
  userInput,
  lessonContext,
  attempt,
  sessionId,
  conversationHistory,
}) {
  const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
  const res = await fetch(`${apiBaseUrl}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_input: userInput,
      lesson_context: lessonContext,
      attempt,
      session_id: sessionId,
      conversation_history: conversationHistory,
    }),
  });
  return res.json();
}
