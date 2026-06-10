import React from "react";
import type { ConsultantMatch } from "../types";

const STATUS_LABELS: Record<string, string> = {
  intercontrat: "Intercontrat",
  en_mission:   "En mission",
  preavailable: "Préavailable",
};
const STATUS_COLORS: Record<string, string> = {
  intercontrat: "var(--ods-success)",
  preavailable: "#f59e0b",
  en_mission:   "var(--ods-text-secondary)",
};
const REMOTE_LABELS: Record<string, string> = {
  full: "Full remote", partial: "Remote partiel", none: "Présentiel",
};

function initials(name: string): string {
  return name.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();
}

function ScoreRing({ score }: { score: number }) {
  const r = 26, circumference = 2 * Math.PI * r;
  return (
    <div style={{ position: "relative", width: 60, height: 60, flexShrink: 0 }}>
      <svg width="60" height="60" viewBox="0 0 60 60">
        <circle cx="30" cy="30" r={r} fill="none" stroke="#eeeeee" strokeWidth="5" />
        <circle cx="30" cy="30" r={r} fill="none" stroke="#FF7900" strokeWidth="5"
          strokeDasharray={circumference} strokeDashoffset={circumference * (1 - score / 100)}
          strokeLinecap="round" transform="rotate(-90 30 30)" />
      </svg>
      <div style={{
        position: "absolute", inset: 0, display: "flex", alignItems: "center",
        justifyContent: "center", fontSize: 14, fontWeight: 500, color: "#FF7900",
      }}>{score}%</div>
    </div>
  );
}

function ScoreBar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11 }}>
      <span style={{ width: 70, color: "var(--ods-text-secondary)", flexShrink: 0 }}>{label}</span>
      <div style={{ flex: 1, height: 4, background: "#eee", borderRadius: 2 }}>
        <div style={{ width: `${(value / max) * 100}%`, height: "100%", background: color, borderRadius: 2 }} />
      </div>
      <span style={{ width: 24, textAlign: "right", color: "var(--ods-text-secondary)" }}>{value}</span>
    </div>
  );
}

export function ConsultantCard({ consultant: c }: { consultant: ConsultantMatch }) {
  const statusColor = STATUS_COLORS[c.status ?? ""] ?? "var(--ods-text-secondary)";
  const statusLabel = STATUS_LABELS[c.status ?? ""] ?? (c.available ? "Disponible" : "En mission");
  const dispoText   = c.availability_date
    ? `Dispo. ${c.availability_date}`
    : (c.available ? statusLabel : `${statusLabel}${c.availability_date ? ` · ${c.availability_date}` : ""}`);

  return (
    <div className="ods-card" style={{ padding: 20 }}>
      <div style={{ display: "flex", gap: 16 }}>
        {/* Avatar */}
        <div style={{
          width: 48, height: 48, borderRadius: "50%", background: "#FF7900",
          display: "flex", alignItems: "center", justifyContent: "center",
          color: "#fff", fontWeight: 500, fontSize: 16, flexShrink: 0,
        }}>{initials(c.name)}</div>

        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Nom + score */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16 }}>
            <div>
              <p style={{ fontWeight: 500, fontSize: 16, color: "#000" }}>{c.name}</p>
              <p style={{ fontSize: 14, color: "var(--ods-text-secondary)", marginTop: 2 }}>{c.title}</p>
            </div>
            <ScoreRing score={c.score} />
          </div>

          {/* Métadonnées : status / localisation / remote / langues / domaines */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, margin: "10px 0 12px" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12 }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: statusColor, flexShrink: 0 }} />
              <span style={{ color: statusColor, fontWeight: 500 }}>{dispoText}</span>
            </span>
            {c.location && (
              <span style={{ fontSize: 12, color: "var(--ods-text-secondary)", background: "#f5f5f5", padding: "2px 8px", borderRadius: 4 }}>
                📍 {c.location}
              </span>
            )}
            {c.remote && (
              <span style={{ fontSize: 12, color: "var(--ods-text-secondary)", background: "#f5f5f5", padding: "2px 8px", borderRadius: 4 }}>
                {REMOTE_LABELS[c.remote] ?? c.remote}
              </span>
            )}
            {c.languages && c.languages.length > 0 && (
              <span style={{ fontSize: 12, color: "var(--ods-text-secondary)", background: "#f5f5f5", padding: "2px 8px", borderRadius: 4 }}>
                {c.languages.map((l) => l.toUpperCase()).join(" · ")}
              </span>
            )}
            {c.domains && c.domains.map((d) => (
              <span key={d} style={{ fontSize: 12, color: "#0055aa", background: "#e8f0fe", padding: "2px 8px", borderRadius: 4 }}>
                {d}
              </span>
            ))}
          </div>

          {/* Skills */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 12 }}>
            {c.matched_skills.map((s) => <span key={s} className="ods-tag-matched">{s}</span>)}
            {c.missing_skills.map((s) => <span key={s} className="ods-tag-missing">{s}</span>)}
          </div>

          {/* Explication IA */}
          <p style={{ fontStyle: "italic", color: "var(--ods-text-secondary)", fontSize: 14, marginBottom: 12, lineHeight: 1.5 }}>
            "{c.explanation}"
          </p>

          {/* Score detail */}
          {c.score_detail && (
            <div style={{ marginBottom: 14, padding: "10px 12px", background: "#f8f8f8", borderRadius: 6, display: "flex", flexDirection: "column", gap: 5 }}>
              <ScoreBar label="Compétences" value={c.score_detail.skills}       max={55} color="#FF7900" />
              <ScoreBar label="Domaine"     value={c.score_detail.domain}       max={25} color="#0055aa" />
              <ScoreBar label="Disponib."   value={c.score_detail.availability} max={15} color="var(--ods-success)" />
              <ScoreBar label="Localisation" value={c.score_detail.location}    max={5}  color="#9a9a9a" />
            </div>
          )}

          {/* Actions */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <div style={{ flex: 1 }} />
            <div style={{ display: "flex", gap: 8 }}>
              <a href={`/api/cvs/${c.cv_filename}`} target="_blank" rel="noreferrer" className="ods-btn-outline">
                Voir le CV
              </a>
              {c.email ? (
                <a href={`mailto:${c.email}`} className="ods-btn-filled-sm">Contacter</a>
              ) : (
                <button type="button" className="ods-btn-filled-sm" disabled>Contacter</button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
