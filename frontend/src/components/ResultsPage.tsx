import React, { useState } from "react";
import { StepIndicator } from "./StepIndicator";
import { RewrittenOffer } from "./RewrittenOffer";
import { ConsultantCard } from "./ConsultantCard";
import { sendResults } from "../api/client";
import type { AnalyzeResponse, ConsultantMatch } from "../types";

type SortKey = "score" | "name" | "available";

interface Props {
  data: AnalyzeResponse;
  onBack: () => void;
}

export function ResultsPage({ data, onBack }: Props) {
  const [sortKey, setSortKey]         = useState<SortKey>("score");
  const [showSend, setShowSend]       = useState(false);
  const [extraEmail, setExtraEmail]   = useState("");
  const [extraList, setExtraList]     = useState<string[]>([]);
  const [sending, setSending]         = useState(false);
  const [sendMsg, setSendMsg]         = useState<{ ok: boolean; text: string } | null>(null);
  const [selected, setSelected]       = useState<Set<string>>(
    () => new Set(data.consultants.map((c) => c.id))
  );

  const sorted = [...data.consultants].sort((a, b) => {
    if (sortKey === "score")     return b.score - a.score;
    if (sortKey === "name")      return a.name.localeCompare(b.name);
    if (sortKey === "available") return Number(b.available) - Number(a.available);
    return 0;
  });

  const toggleSelect = (id: string) =>
    setSelected((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const addExtra = () => {
    if (!extraEmail.includes("@")) return;
    setExtraList((l) => [...new Set([...l, extraEmail.trim()])]);
    setExtraEmail("");
  };

  const handleSend = async () => {
    const toSend: ConsultantMatch[] = data.consultants.filter((c) => selected.has(c.id));
    if (toSend.length === 0) return;
    setSending(true);
    setSendMsg(null);
    try {
      const res = await sendResults({ offer: data.rewritten_offer, consultants: toSend, extra_recipients: extraList });
      setSendMsg({ ok: res.success, text: res.message });
    } catch (e: unknown) {
      setSendMsg({ ok: false, text: e instanceof Error ? e.message : "Erreur d'envoi" });
    }
    setSending(false);
  };

  return (
    <div className="ods-fade-in" style={{ background: "var(--ods-surface)", minHeight: "calc(100vh - 56px)", padding: "28px 0 80px" }}>
      <div className="ods-container-wide">
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
          <StepIndicator active={2} />
          <div style={{ flex: 1 }} />
          <button type="button" className="ods-tlink" onClick={onBack}>← Modifier la mission</button>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "340px 1fr", gap: 24, alignItems: "start" }}>
          {/* Panneau gauche — sticky */}
          <div style={{ position: "sticky", top: 73 }}>
            <RewrittenOffer offer={data.rewritten_offer} onEdit={onBack} />
          </div>

          {/* Panneau droit */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18, gap: 12, flexWrap: "wrap" }}>
              <p style={{ fontSize: 19 }}>
                <strong style={{ fontWeight: 500 }}>{data.consultants.length} consultant{data.consultants.length > 1 ? "s" : ""}</strong> matchés
              </p>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <select className="ods-select" value={sortKey} onChange={(e) => setSortKey(e.target.value as SortKey)}>
                  <option value="score">Trier par score</option>
                  <option value="available">Trier par disponibilité</option>
                  <option value="name">Trier par nom</option>
                </select>
                <button type="button" className="ods-btn-primary" style={{ fontSize: 14, padding: "8px 16px" }}
                  onClick={() => { setShowSend(true); setSendMsg(null); }}>
                  ✉ Envoyer au staffing
                </button>
              </div>
            </div>

            {/* Panneau envoi email */}
            {showSend && (
              <div className="ods-card" style={{ padding: 20, marginBottom: 20, background: "#fffdf5", border: "1px solid #f59e0b" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                  <strong style={{ fontSize: 15 }}>Envoyer la shortlist au pôle staffing</strong>
                  <button type="button" onClick={() => setShowSend(false)}
                    style={{ background: "none", border: "none", cursor: "pointer", fontSize: 18, color: "#999" }}>×</button>
                </div>

                <p style={{ fontSize: 13, color: "var(--ods-text-secondary)", marginBottom: 12 }}>
                  Sélectionnez les consultants à inclure :
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 16 }}>
                  {data.consultants.map((c) => (
                    <label key={c.id} style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 14 }}>
                      <input type="checkbox" checked={selected.has(c.id)} onChange={() => toggleSelect(c.id)} />
                      <strong>{c.name}</strong>
                      <span style={{ color: "var(--ods-text-secondary)" }}>— {c.title}</span>
                      <span style={{ marginLeft: "auto", color: "#FF7900", fontWeight: 500 }}>{c.score}%</span>
                    </label>
                  ))}
                </div>

                <div style={{ marginBottom: 14 }}>
                  <label className="ods-label">Destinataires supplémentaires</label>
                  <div style={{ display: "flex", gap: 8 }}>
                    <input className="ods-input" placeholder="email@exemple.com"
                      value={extraEmail} onChange={(e) => setExtraEmail(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && addExtra()} style={{ flex: 1 }} />
                    <button type="button" className="ods-btn-outline" onClick={addExtra}>Ajouter</button>
                  </div>
                  {extraList.length > 0 && (
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
                      {extraList.map((e) => (
                        <span key={e} onClick={() => setExtraList((l) => l.filter((x) => x !== e))}
                          style={{ fontSize: 12, background: "#e8f0fe", color: "#0055aa", padding: "2px 8px",
                            borderRadius: 4, cursor: "pointer" }}>
                          {e} ×
                        </span>
                      ))}
                    </div>
                  )}
                  <p style={{ fontSize: 12, color: "var(--ods-text-secondary)", marginTop: 6 }}>
                    Les destinataires configurés dans Administration seront également notifiés.
                  </p>
                </div>

                {sendMsg && (
                  <div style={{
                    padding: "10px 14px", borderRadius: 6, marginBottom: 12, fontSize: 13,
                    background: sendMsg.ok ? "#f0fdf4" : "#fff0ee",
                    color: sendMsg.ok ? "var(--ods-success)" : "var(--ods-error)",
                    border: `1px solid ${sendMsg.ok ? "var(--ods-success)" : "var(--ods-error)"}`,
                  }}>
                    {sendMsg.ok ? "✓ " : "✗ "}{sendMsg.text}
                  </div>
                )}

                <button type="button" className="ods-btn-primary" onClick={handleSend}
                  disabled={sending || selected.size === 0} style={{ fontSize: 14 }}>
                  {sending ? "Envoi en cours…" : `Envoyer ${selected.size} consultant${selected.size > 1 ? "s" : ""}`}
                </button>
              </div>
            )}

            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {sorted.map((c) => <ConsultantCard key={c.id} consultant={c} />)}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
