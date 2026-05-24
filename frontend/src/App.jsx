import { useState, useEffect } from "react";
import "./App.css";
import StudentApp from "./student";
import AdminApp from "./admin";

// Determines which view to show based on the URL hash.
// Visit /#/admin for the admin dashboard; everything else shows the student view.
function getView() {
  return window.location.hash === "#/admin" ? "admin" : "student";
}

export default function App() {
  const [view, setView] = useState(getView);

  useEffect(() => {
    const onHash = () => setView(getView());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  return view === "admin" ? <AdminApp /> : <StudentApp />;
}
