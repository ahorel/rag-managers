import React, { useEffect, useRef, useState } from "react";
import { NavBar } from "./components/NavBar";
import { MissionInput } from "./components/MissionInput";
import { ResultsPage } from "./components/ResultsPage";
import { AdminConfig } from "./components/AdminConfig";
import { AdminGate } from "./components/AdminGate";
import { analyzeMission, checkHealth } from "./api/client";
import type { AnalyzeRequest, AnalyzeResponse } from "./types";

type Screen = "input" | "analyzing" | "results" | "admin";

const ANALYZE_LINES = [
  "Lecture de l'expression de besoin…",
  "Extraction des compétences clés…",
  "Génération de la fiche de poste…",
  "Comparaison aux CVs disponibles…",
];

function AnalyzingScreen() {
  const [step, setStep] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval>>();
  useEffect(() => {
    timerRef.current = setInterval(() => setStep((s) => Math.min(s + 1, ANALYZE_LINES.length - 1)), 420);
    return () => clearInterval(timerRef.current);
  }, []);
  return (
    <div className="ods-fade-in" style={{
      minHeight: "calc(100vh - 56px)", background: "var(--ods-surface)",
      display: "flex", alignItems: "center", justifyContent: "center", padding: 24,
    }}>
      <div className="ods-card" style={{ width: 460, padding: 32, textAlign: "center" }}>
        <div className="ods-spinner-lg" style={{ margin: "0 auto 22px" }} />
        <div style={{ fontSize: 18, fontWeight: 500, marginBottom: 6 }}>Analyse en cours</div>
        <p style={{ color: "var(--ods-text-secondary)", fontSize: 13, marginBottom: 22 }}>
          Génération de la fiche de poste et matching des consultants
        </p>
        <div className="ods-pulse-bar" style={{ marginBottom: 20 }}><i /></div>
        <div style={{ textAlign: "left", display: "flex", flexDirection: "column", gap: 8 }}>
          {ANALYZE_LINES.map((line, i) => (
            <div key={line} style={{
              display: "flex", alignItems: "center", gap: 8, fontSize: 13,
              color: i <= step ? "var(--ods-text-primary)" : "var(--ods-text-secondary)",
            }}>
              <span style={{ color: i < step ? "var(--ods-success)" : "var(--ods-border)" }}>
                {i < step ? "✓" : "○"}
              </span>
              {line}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [screen, setScreen]         = useState<Screen>("input");
  const [results, setResults]       = useState<AnalyzeResponse | null>(null);
  const [error, setError]           = useState<string | null>(null);
  const [totalCvs, setTotalCvs]     = useState(0);
  const [adminUnlocked, setAdminUnlocked] = useState(false);
  const [showGate, setShowGate]     = useState(false);

  useEffect(() => {
    checkHealth().then((h) => setTotalCvs(h.cvs_loaded)).catch(() => {});
  }, []);

  const handleSubmit = async (req: AnalyzeRequest) => {
    setError(null);
    setScreen("analyzing");
    try {
      const data = await analyzeMission(req);
      setResults(data);
      setTotalCvs(data.total_cvs);
      setScreen("results");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur inattendue");
      setScreen("input");
    }
  };

  const handleBack  = () => { setScreen("input"); setError(null); };
  const handleHome  = () => { setScreen("input"); setError(null); };
  const handleAdmin = () => {
    if (screen === "admin") { setScreen("input"); return; }
    if (adminUnlocked) { setScreen("admin"); return; }
    setShowGate(true);
  };

  return (
    <>
      <NavBar onAdmin={handleAdmin} isAdmin={screen === "admin"} onHome={handleHome} />
      {showGate && (
        <AdminGate
          onUnlock={() => { setAdminUnlocked(true); setShowGate(false); setScreen("admin"); }}
          onCancel={() => setShowGate(false)}
        />
      )}

      {error && (
        <div style={{
          background: "#fff0ee", border: "1px solid var(--ods-error)",
          color: "var(--ods-error)", padding: "12px 24px", fontSize: 14,
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <span>Erreur : {error}</span>
          <button type="button" onClick={() => setError(null)}
            style={{ background: "none", border: "none", cursor: "pointer", color: "var(--ods-error)", fontSize: 18 }}>×</button>
        </div>
      )}

      {screen === "input"     && <MissionInput onSubmit={handleSubmit} loading={false} totalCvs={totalCvs} />}
      {screen === "analyzing" && <AnalyzingScreen />}
      {screen === "results"   && results && <ResultsPage data={results} onBack={handleBack} />}
      {screen === "admin"     && <AdminConfig />}
    </>
  );
}
