import React from "react";

interface Props {
  onAdmin: () => void;
  isAdmin: boolean;
  onHome: () => void;
}

export function NavBar({ onAdmin, isAdmin, onHome }: Props) {
  return (
    <nav style={{
      background: "#000", height: 56, display: "flex", alignItems: "center",
      padding: "0 24px", gap: 16, position: "sticky", top: 0, zIndex: 100,
    }}>
      <button
        type="button"
        onClick={onHome}
        style={{ background: "none", border: "none", cursor: "pointer", display: "flex", alignItems: "center", gap: 12, padding: 0 }}
      >
        <div style={{
          width: 32, height: 32, borderRadius: 2, background: "#FF7900",
          display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
        }}>
          <span style={{ color: "#fff", fontWeight: 700, fontSize: 18, lineHeight: 1 }}>m</span>
        </div>
        <span style={{ color: "#fff", fontWeight: 500, fontSize: 16, letterSpacing: "0.01em" }}>
          MatchConsult
        </span>
      </button>

      <div style={{ width: 1, height: 24, background: "#333", flexShrink: 0 }} />
      <span style={{ color: "#9a9a9a", fontSize: 13 }}>Orange Business · Sourcing ESN</span>

      <div style={{ flex: 1 }} />

      <button
        type="button"
        onClick={onAdmin}
        style={{
          background: isAdmin ? "#222" : "none",
          border: isAdmin ? "1px solid #444" : "1px solid #333",
          borderRadius: 6,
          color: isAdmin ? "#FF7900" : "#9a9a9a",
          fontSize: 13,
          fontWeight: 500,
          padding: "6px 14px",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          gap: 6,
        }}
      >
        ⚙ Administration
      </button>

      <div style={{
        width: 36, height: 36, borderRadius: "50%", background: "#2a2a2a",
        border: "1px solid #444", display: "flex", alignItems: "center",
        justifyContent: "center", color: "#fff", fontWeight: 500, fontSize: 13, flexShrink: 0,
      }}>
        JM
      </div>
    </nav>
  );
}
