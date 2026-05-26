import React, { useState } from "react";
import { colors } from "../student/styles/theme";
import Sidebar from "./components/Sidebar";
import OverviewPage from "./pages/Overview";
import CurriculumPage from "./pages/Curriculum";
import AuditLogPage from "./pages/AuditLog";
import AskPage from "./pages/Ask";

const PAGES = {
  overview:   OverviewPage,
  curriculum: CurriculumPage,
  audit:      AuditLogPage,
  ask:        AskPage,
};

// Admin root: sidebar nav + scrollable content area.
// Navigate here by visiting /#/admin in the browser.
export default function AdminApp() {
  const [activePage, setActivePage] = useState("overview");

  const PageComponent = PAGES[activePage] ?? OverviewPage;

  return (
    <div style={{
      display: "flex",
      minHeight: "100vh",
      background: colors.bg,
      color: colors.text,
      fontFamily: "Inter, system-ui, sans-serif",
    }}>
      <Sidebar activePage={activePage} onNavigate={setActivePage} />

      {/* Main content — scrolls independently of the fixed sidebar */}
      <main style={{ flex: 1, overflowY: "auto" }}>
        <PageComponent />
      </main>
    </div>
  );
}
