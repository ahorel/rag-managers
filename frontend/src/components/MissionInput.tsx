import React, { useEffect, useState } from "react";
import { StepIndicator } from "./StepIndicator";
import { getDomains } from "../api/client";
import type { AnalyzeRequest } from "../types";

const EXAMPLES = ["Dev Java Senior", "Chef de projet MOA", "Architecte Cloud"];
const SAMPLES: Record<string, string> = {
  "Dev Java Senior":
    "Bonjour, nous avons besoin d'un développeur Java senior pour une mission de 6 mois à Paris dans le secteur bancaire. Stack Java 17, Spring Boot, microservices. Démarrage début juillet, anglais courant requis, remote partiel possible.",
  "Chef de projet MOA":
    "Recherche chef de projet MOA pour piloter la transformation digitale d'une direction métier dans le secteur assurance à Lyon. Conduite du changement, specs fonctionnelles, coordination DSI. Mission forfait 12 mois, français uniquement.",
  "Architecte Cloud":
    "Besoin urgent d'un architecte Cloud Azure/AWS pour migration infrastructure on-premise vers le cloud dans le secteur télécom. 7+ ans d'expérience, certifications cloud, remote full accepté.",
};

const REMOTE_OPTIONS = [
  { value: "", label: "Indifférent" },
  { value: "full", label: "Full remote" },
  { value: "partial", label: "Remote partiel" },
  { value: "none", label: "Présentiel uniquement" },
];

interface Props {
  onSubmit: (req: AnalyzeRequest) => void;
  loading: boolean;
  totalCvs: number;
}

export function MissionInput({ onSubmit, loading, totalCvs }: Props) {
  const [text, setText]                   = useState("");
  const [showAdvanced, setShowAdvanced]   = useState(false);
  const [availability, setAvailability]   = useState("");
  const [priorityInput, setPriorityInput] = useState("");
  const [prioritySkills, setPrioritySkills] = useState<string[]>([]);
  const [maxResults, setMaxResults]       = useState(10);
  const [domain, setDomain]               = useState("");
  const [location, setLocation]           = useState("");
  const [remote, setRemote]               = useState("");
  const [langFr, setLangFr]               = useState(false);
  const [langEn, setLangEn]               = useState(false);
  const [intercontratOnly, setIntercontratOnly] = useState(false);
  const [domains, setDomains]             = useState<string[]>([]);

  useEffect(() => {
    getDomains().then((r) => setDomains(r.domains)).catch(() => {});
  }, []);

  const handleAddSkill = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && priorityInput.trim()) {
      setPrioritySkills((p) => [...p, priorityInput.trim()]);
      setPriorityInput("");
    }
  };

  const handleSubmit = () => {
    if (!text.trim() || loading) return;
    const langs: string[] = [];
    if (langFr) langs.push("fr");
    if (langEn) langs.push("en");
    onSubmit({
      mission_text: text,
      required_availability: availability || undefined,
      priority_skills: prioritySkills.length > 0 ? prioritySkills : undefined,
      max_results: maxResults,
      filter_domain: domain || undefined,
      filter_location: location || undefined,
      filter_remote: remote || undefined,
      filter_languages: langs.length > 0 ? langs : undefined,
      filter_intercontrat_only: intercontratOnly,
    });
  };

  return (
    <div className="ods-container ods-page ods-fade-in">
      <div className="ods-card" style={{ padding: 32 }}>
        <StepIndicator active={1} />
        <div style={{ height: 1, background: "var(--ods-border)", margin: "24px 0" }} />

        <h2 className="ods-section-title">Expression de besoin du client</h2>

        <div style={{ marginBottom: 16 }}>
          <label className="ods-label" htmlFor="mission-textarea">
            Copiez-collez l'email ou la description du client
          </label>
          <textarea
            id="mission-textarea"
            className="ods-textarea"
            placeholder="Copiez-collez l'email client tel quel — localisation, langue, disponibilité, périmètre métier, compétences recherchées…&#10;&#10;La solution génèrera automatiquement la fiche de poste et trouvera les consultants les plus adaptés."
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={loading}
          />
        </div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 24 }}>
          <span className="ods-label" style={{ marginRight: 4 }}>Exemples :</span>
          {EXAMPLES.map((ex) => (
            <button key={ex} className="ods-chip" onClick={() => setText(SAMPLES[ex] ?? ex)}
              disabled={loading} type="button">+ {ex}</button>
          ))}
        </div>

        {/* Options avancées */}
        <div style={{ marginBottom: 24 }}>
          <button type="button" className={"ods-collapse-head" + (showAdvanced ? " open" : "")}
            onClick={() => setShowAdvanced((v) => !v)}>
            <span>Filtres de recherche</span>
            <span className="chev">▾</span>
          </button>

          {showAdvanced && (
            <div className="ods-collapse-body">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}>
                {/* Domaine */}
                <div>
                  <label className="ods-label">Domaine métier</label>
                  <select className="ods-select" value={domain} onChange={(e) => setDomain(e.target.value)}>
                    <option value="">Auto-détecté depuis le texte</option>
                    {domains.map((d) => (
                      <option key={d} value={d}>{d.charAt(0).toUpperCase() + d.slice(1)}</option>
                    ))}
                  </select>
                </div>

                {/* Remote */}
                <div>
                  <label className="ods-label">Télétravail</label>
                  <select className="ods-select" value={remote} onChange={(e) => setRemote(e.target.value)}>
                    {REMOTE_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                </div>

                {/* Localisation */}
                <div>
                  <label className="ods-label">Localisation</label>
                  <input className="ods-input" placeholder="Paris, Lyon, Bordeaux…"
                    value={location} onChange={(e) => setLocation(e.target.value)} />
                </div>

                {/* Disponibilité */}
                <div>
                  <label className="ods-label">Disponible avant le</label>
                  <input type="date" className="ods-input" value={availability}
                    onChange={(e) => setAvailability(e.target.value)} />
                </div>
              </div>

              {/* Langues + intercontrat */}
              <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginBottom: 20 }}>
                <div>
                  <label className="ods-label">Langues requises</label>
                  <div style={{ display: "flex", gap: 16, marginTop: 8 }}>
                    {[["fr", "Français", langFr, setLangFr], ["en", "Anglais", langEn, setLangEn]].map(
                      ([val, label, checked, setter]) => (
                        <label key={val as string} style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer", fontSize: 14 }}>
                          <input type="checkbox" checked={checked as boolean}
                            onChange={(e) => (setter as (v: boolean) => void)(e.target.checked)} />
                          {label as string}
                        </label>
                      )
                    )}
                  </div>
                </div>

                <div>
                  <label className="ods-label">Statut</label>
                  <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer", fontSize: 14, marginTop: 8 }}>
                    <input type="checkbox" checked={intercontratOnly}
                      onChange={(e) => setIntercontratOnly(e.target.checked)} />
                    Intercontrat uniquement
                  </label>
                </div>
              </div>

              {/* Compétences prioritaires */}
              <div style={{ marginBottom: 20 }}>
                <label className="ods-label">Compétences prioritaires</label>
                <input className="ods-input" placeholder="Tapez une compétence et appuyez sur Entrée…"
                  value={priorityInput} onChange={(e) => setPriorityInput(e.target.value)}
                  onKeyDown={handleAddSkill} />
                {prioritySkills.length > 0 && (
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
                    {prioritySkills.map((s) => (
                      <span key={s} onClick={() => setPrioritySkills((p) => p.filter((x) => x !== s))}
                        style={{ display: "inline-flex", alignItems: "center", gap: 6, height: 28,
                          padding: "0 10px", background: "var(--ods-surface)", border: "1px solid var(--ods-border)",
                          borderRadius: "var(--ods-radius)", fontSize: 13, cursor: "pointer" }}>
                        {s} <span style={{ opacity: 0.6, fontSize: 14 }}>×</span>
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Nombre de résultats */}
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                  <label className="ods-label">Nombre de résultats</label>
                  <span style={{ fontWeight: 500, color: "var(--ods-orange)", fontSize: 14 }}>{maxResults}</span>
                </div>
                <input type="range" min={3} max={20} value={maxResults}
                  onChange={(e) => setMaxResults(Number(e.target.value))}
                  style={{ width: "100%", accentColor: "#FF7900" }} />
                <div style={{ display: "flex", justifyContent: "space-between", color: "var(--ods-text-secondary)", fontSize: 11, marginTop: 4 }}>
                  <span>3</span><span>20</span>
                </div>
              </div>
            </div>
          )}
        </div>

        <button className="ods-btn-primary" onClick={handleSubmit}
          disabled={!text.trim() || loading} type="button" style={{ fontSize: 16 }}>
          {loading && <span className="ods-spinner" />}
          {loading ? "Analyse en cours…" : "Générer la fiche et matcher les consultants →"}
        </button>

        <p style={{ textAlign: "center", marginTop: 12, fontSize: 13, color: "#999" }}>
          {totalCvs > 0
            ? `Le système va générer la fiche de poste et la comparer à ${totalCvs} CVs disponibles`
            : "Chargement des CVs en cours…"}
        </p>
      </div>
    </div>
  );
}
