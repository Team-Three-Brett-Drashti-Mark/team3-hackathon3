import { useState, useEffect } from "react";
import "./App.css";
import LandingPage from "./landing";
import StudentApp from "./student";
import AdminApp from "./admin";

// Determines which view to show based on the URL hash.
//   #/admin   → admin dashboard
//   #/student → student learning platform
//   anything else (empty hash, #/, etc.) → the landing page entry point
// Keeping this hash-based keeps the deployment a single static SPA with no
// server-side routing, which is what the Render single-service setup expects.
function getView() {
  if (window.location.hash === "#/admin") return "admin";
  if (window.location.hash === "#/student") return "student";
  return "landing";
}

export default function App() {
  const [view, setView] = useState(getView);

  useEffect(() => {
    const onHash = () => setView(getView());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  if (view === "admin") return <AdminApp />;
  if (view === "student") return <StudentApp />;
  return <LandingPage />;
}
