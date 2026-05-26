import React from "react";
import { colors } from "../../../student/styles/theme";

const FOLDERS = [
  { name: "markdown", emoji: "📝", description: "Lesson notes and reading material" },
  { name: "pdfs",     emoji: "📄", description: "PDF handouts and references" },
  { name: "quizzes",  emoji: "📋", description: "Quiz files and rubrics" },
];

// Three folder cards for a selected week. Clicking a card drills into that folder.
export default function FolderView({ weekName, onSelect }) {
  return (
    <div>
      <h2 style={{ margin: "0 0 20px", fontSize: 18, fontWeight: 700, color: "#1e1c18" }}>
        {weekName}
      </h2>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
        {FOLDERS.map((folder) => (
          <button
            key={folder.name}
            onClick={() => onSelect(folder.name)}
            style={{
              background: colors.surface,
              border: `1px solid ${colors.border}`,
              borderRadius: 8,
              padding: "22px 18px",
              cursor: "pointer",
              textAlign: "left",
              display: "flex",
              flexDirection: "column",
              gap: 8,
              transition: "border-color 0.15s, box-shadow 0.15s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = colors.accent;
              e.currentTarget.style.boxShadow = `0 0 0 2px ${colors.accent}22`;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = colors.border;
              e.currentTarget.style.boxShadow = "none";
            }}
          >
            <span style={{ fontSize: 28 }}>{folder.emoji}</span>
            <div style={{ fontSize: 14, fontWeight: 700, color: colors.text }}>
              {folder.name}/
            </div>
            <div style={{ fontSize: 12, color: colors.muted, lineHeight: 1.4 }}>
              {folder.description}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
