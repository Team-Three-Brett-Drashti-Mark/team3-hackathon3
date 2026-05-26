import React from "react";
import { colors } from "../../../student/styles/theme";

// Placeholder — natural-language query interface over interaction data + curriculum.
// Coming soon.
export default function AskPage() {
  return (
    <div style={{ padding: "28px 32px", maxWidth: 720 }}>
      <h1 style={{ margin: "0 0 8px", fontSize: 22, fontWeight: 800, color: colors.text }}>Ask</h1>
      <p style={{ margin: 0, fontSize: 14, color: colors.muted, lineHeight: 1.65 }}>
        Ask questions about student interaction patterns and curriculum coverage in plain English.
        This feature is coming soon.
      </p>
    </div>
  );
}
