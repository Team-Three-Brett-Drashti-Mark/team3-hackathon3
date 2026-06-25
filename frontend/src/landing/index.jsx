import React, { useState } from "react";
import { colors, labelStyle } from "../student/styles/theme";
import heroImage from "../assets/landing-hero.png";

// Landing page is the default entry point (empty hash). It funnels visitors
// into one of the two real apps via hash navigation, so it intentionally owns
// no app state — it only flips window.location.hash, which App.jsx listens for.
//
// Styling deliberately reuses the shared `colors`/`labelStyle` tokens and the
// dark top bar from the student Navbar so the landing screen reads as the same
// product, not a separate site.

// Each destination card is described by data so the markup stays a single
// mapped block — keeps the two cards visually identical and easy to extend.
const DESTINATIONS = [
  {
    id: "student",
    hash: "#/student",
    eyebrow: "Student",
    title: "Learning Platform",
    body:
      "Ask questions in plain language and get guided coaching — never copy-paste " +
      "answers. Work through the curriculum with lessons, quizzes, and a tutor that " +
      "helps you think it through.",
    cta: "Open the learning platform",
    // Cold start only affects the admin/data path, so this stays null here.
    note: null,
  },
  {
    id: "admin",
    hash: "#/admin",
    eyebrow: "Admin",
    title: "Insights Dashboard",
    body:
      "See what students are actually asking, where they get stuck, and which parts " +
      "of the curriculum are referenced most. Manage curriculum files and review the " +
      "guardrail audit log.",
    cta: "Open the admin dashboard",
    // Surfaced on the card itself so admins aren't surprised by the first-load
    // latency of the serverless community backend.
    note:
      "Heads up: the admin dashboard runs on the serverless Databricks Community " +
      "edition, so the first request after it goes idle can take ~30–60 seconds to " +
      "warm up. Give it a moment on the initial load.",
  },
];

// A single destination card. Hover state lifts the card and brightens its
// border to the gold accent — the only interactive affordance on the page, so
// it's worth making obvious.
function DestinationCard({ dest }) {
  const [hover, setHover] = useState(false);

  const go = () => {
    window.location.hash = dest.hash;
  };

  return (
    <button
      onClick={go}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        flex: "1 1 320px",
        maxWidth: 420,
        textAlign: "left",
        cursor: "pointer",
        display: "flex",
        flexDirection: "column",
        gap: 14,
        padding: "26px 26px 24px",
        borderRadius: 14,
        background: colors.surface,
        border: `1px solid ${hover ? colors.accent : colors.border}`,
        // Subtle lift on hover; transform is GPU-cheap and avoids reflow.
        transform: hover ? "translateY(-4px)" : "translateY(0)",
        boxShadow: hover
          ? "0 12px 28px rgba(30,28,24,0.14)"
          : "0 2px 8px rgba(30,28,24,0.06)",
        transition: "transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease",
        font: "inherit",
        color: colors.text,
      }}
    >
      <span style={labelStyle}>{dest.eyebrow}</span>

      <h2 style={{ margin: 0, fontSize: 24, fontWeight: 800, lineHeight: 1.15 }}>
        {dest.title}
      </h2>

      <p style={{ margin: 0, fontSize: 15, lineHeight: 1.55, color: colors.text }}>
        {dest.body}
      </p>

      {dest.note && (
        <p
          style={{
            margin: 0,
            fontSize: 13,
            lineHeight: 1.5,
            color: colors.muted,
            background: "rgba(236,192,88,0.12)",
            border: "1px solid rgba(236,192,88,0.3)",
            borderRadius: 8,
            padding: "10px 12px",
          }}
        >
          {dest.note}
        </p>
      )}

      {/* Pushed to the bottom so both cards align their CTA regardless of body
          length difference. */}
      <span
        style={{
          marginTop: "auto",
          paddingTop: 6,
          fontSize: 14,
          fontWeight: 700,
          color: colors.accentText,
          background: colors.accent,
          alignSelf: "flex-start",
          padding: "9px 16px",
          borderRadius: 8,
        }}
      >
        {dest.cta} →
      </span>
    </button>
  );
}

export default function LandingPage() {
  return (
    <div
      style={{
        background: colors.bg,
        minHeight: "100vh",
        color: colors.text,
        fontFamily: "Inter, system-ui, sans-serif",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Top bar — mirrors the student Navbar so branding is consistent. */}
      <div
        style={{
          height: 52,
          background: colors.nav,
          borderBottom: `2px solid ${colors.accent}`,
          display: "flex",
          alignItems: "center",
          padding: "0 20px",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 6,
              background: colors.accent,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 13,
              fontWeight: 900,
              color: colors.nav,
              flexShrink: 0,
            }}
          >
            P
          </div>
          <span style={{ color: colors.navText, fontWeight: 700, fontSize: 15 }}>
            Pathwise
          </span>
        </div>
      </div>

      {/* Hero + cards, centered with a comfortable max width. */}
      <div
        style={{
          flex: 1,
          width: "100%",
          maxWidth: 980,
          margin: "0 auto",
          padding: "48px 24px 64px",
          boxSizing: "border-box",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 36,
        }}
      >
        {/* Hero image carries the brand visual; decorative, so empty alt. */}
        <img
          src={heroImage}
          alt=""
          style={{
            width: "100%",
            maxWidth: 620,
            height: "auto",
            borderRadius: 14,
            // Blend the image's cream background into the page so it reads as
            // an illustration rather than a pasted screenshot with hard edges.
            mixBlendMode: "multiply",
          }}
        />

        <div style={{ textAlign: "center", maxWidth: 640 }}>
          <h1 style={{ margin: "0 0 12px", fontSize: 44, fontWeight: 900, letterSpacing: "-0.5px" }}>
            Pathwise
          </h1>
          <p style={{ margin: 0, fontSize: 19, lineHeight: 1.5, color: colors.muted }}>
            A learning system designed for active problem solving.
          </p>
        </div>

        {/* Two destination cards — the "two tabs" entry points. */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 20,
            justifyContent: "center",
            width: "100%",
          }}
        >
          {DESTINATIONS.map((dest) => (
            <DestinationCard key={dest.id} dest={dest} />
          ))}
        </div>
      </div>
    </div>
  );
}
