import React, { useEffect, useState, useCallback } from "react";
import { getAdminConfig, updateAdminConfig } from "../api/client";
import type { AdminConfig as AdminConfigType, AppConfig, EmailConfig } from "../types";

const GROQ_MODELS = [
  "llama-3.1-8b-instant",
  "llama3-70b-8192",
  "mixtral-8x7b-32768",
  "gemma2-9b-it",
];

/* ---- Inline helper subcomponents ---- */

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="ods-card" style={{ padding: 28, marginBottom: 20 }}>
      <h3 style={{ fontSize: 16, fontWeight: 500, marginBottom: 20, paddingBottom: 12, borderBottom: "1px solid var(--ods-border)" }}>
        {title}
      </h3>
      {children}
    </div>
  );
}

function FieldRow({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 16 }}>
      {children}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="ods-label">{label}</label>
      {children}
    </div>
  );
}

function TagList({
  items, onRemove, placeholder,
}: { items: string[]; onRemove: (item: string) => void; placeholder?: string }) {
  const [input, setInput] = useState("");
  return (
    <>
      <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
        <input className="ods-input" placeholder={placeholder ?? "Ajouter…"} value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && input.trim()) { onRemove("__add__" + input.trim()); setInput(""); } }}
          style={{ flex: 1 }} />
        <button type="button" className="ods-btn-outline"
          onClick={() => { if (input.trim()) { onRemove("__add__" + input.trim()); setInput(""); } }}>
          Ajouter
        </button>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {items.map((item) => (
          <span key={item} onClick={() => onRemove(item)}
            style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13,
              background: "#f5f5f5", border: "1px solid var(--ods-border)", borderRadius: 20,
              padding: "3px 10px 3px 12px", cursor: "pointer" }}>
            {item}
            <span style={{ fontSize: 14, opacity: 0.5, lineHeight: 1 }}>×</span>
          </span>
        ))}
      </div>
    </>
  );
}

function CustomSimInput({ onAdd }: { onAdd: (d: string) => void }) {
  const [v, setV] = useState("");
  const commit = () => { if (v.trim()) { onAdd(v.trim()); setV(""); } };
  return (
    <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
      <input className="ods-input" placeholder="domaine personnalisé…" value={v}
        onChange={(e) => setV(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && commit()}
        style={{ flex: 1 }} />
      <button type="button" className="ods-btn-outline" onClick={commit}>Ajouter</button>
    </div>
  );
}

/* ---- Main component ---- */

export function AdminConfig() {
  const [app, setApp]       = useState<AppConfig | null>(null);
  const [email, setEmail]   = useState<EmailConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg]       = useState<{ ok: boolean; text: string } | null>(null);

  /* domain similarity editor state */
  const [simDomain, setSimDomain] = useState(""); // which domain is being edited

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const cfg: AdminConfigType = await getAdminConfig();
      setApp(cfg.app);
      setEmail(cfg.email);
    } catch (e: unknown) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Erreur de chargement" });
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    if (!app || !email) return;
    setSaving(true);
    setMsg(null);
    try {
      await updateAdminConfig({ app, email });
      setMsg({ ok: true, text: "Configuration enregistrée." });
    } catch (e: unknown) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Erreur d'enregistrement" });
    }
    setSaving(false);
  };

  /* --- App config helpers --- */
  const setAppField = <K extends keyof AppConfig>(key: K, value: AppConfig[K]) =>
    setApp((a) => a ? { ...a, [key]: value } : a);

  /* Domain list */
  const handleDomainTag = (action: string) => {
    if (!app) return;
    if (action.startsWith("__add__")) {
      const d = action.slice(7).toLowerCase().trim();
      if (d && !app.domain_list.includes(d))
        setApp({ ...app, domain_list: [...app.domain_list, d] });
    } else {
      setApp({ ...app, domain_list: app.domain_list.filter((x) => x !== action) });
    }
  };

  /* Domain similar groups */
  const handleSimilarTag = (forDomain: string, action: string) => {
    if (!app) return;
    const cur = app.domain_similar[forDomain] ?? [];
    let next: string[];
    if (action.startsWith("__add__")) {
      const d = action.slice(7).toLowerCase().trim();
      next = d && !cur.includes(d) ? [...cur, d] : cur;
    } else {
      next = cur.filter((x) => x !== action);
    }
    setApp({ ...app, domain_similar: { ...app.domain_similar, [forDomain]: next } });
  };

  /* --- Email config helpers --- */
  const setEmailField = <K extends keyof EmailConfig>(key: K, value: EmailConfig[K]) =>
    setEmail((e) => e ? { ...e, [key]: value } : e);

  const handleRecipientTag = (action: string) => {
    if (!email) return;
    if (action.startsWith("__add__")) {
      const r = action.slice(7).trim();
      if (r.includes("@") && !email.recipients.includes(r))
        setEmail({ ...email, recipients: [...email.recipients, r] });
    } else {
      setEmail({ ...email, recipients: email.recipients.filter((x) => x !== action) });
    }
  };

  /* ---- Render ---- */

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: 60 }}>
        <span className="ods-spinner-lg" />
      </div>
    );
  }

  if (!app || !email) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "var(--ods-error)" }}>
        Impossible de charger la configuration.
        <button className="ods-tlink" style={{ marginLeft: 12 }} onClick={load}>Réessayer</button>
      </div>
    );
  }

  return (
    <div className="ods-fade-in" style={{ background: "var(--ods-surface)", minHeight: "calc(100vh - 56px)", padding: "28px 0 80px" }}>
      <div className="ods-container">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
          <div>
            <h2 style={{ fontSize: 22, fontWeight: 500 }}>Administration</h2>
            <p style={{ fontSize: 13, color: "var(--ods-text-secondary)", marginTop: 4 }}>
              Configuration de l'application — modifiable à la volée
            </p>
          </div>
          <button type="button" className="ods-btn-primary" onClick={save}
            disabled={saving} style={{ fontSize: 14, minWidth: 140 }}>
            {saving ? "Enregistrement…" : "Enregistrer tout"}
          </button>
        </div>

        {msg && (
          <div style={{
            padding: "12px 16px", borderRadius: 6, marginBottom: 20, fontSize: 14,
            background: msg.ok ? "#f0fdf4" : "#fff0ee",
            color: msg.ok ? "var(--ods-success)" : "var(--ods-error)",
            border: `1px solid ${msg.ok ? "var(--ods-success)" : "var(--ods-error)"}`,
          }}>
            {msg.ok ? "✓ " : "✗ "}{msg.text}
          </div>
        )}

        {/* ── Section 1 : LLM ──────────────────────────────────────── */}
        <Section title="🤖 Configuration LLM">
          <FieldRow>
            <Field label="Clé API Groq">
              <input className="ods-input" type="password" placeholder="gsk_…"
                value={app.groq_api_key}
                onChange={(e) => setAppField("groq_api_key", e.target.value)} />
              <p style={{ fontSize: 11, color: "var(--ods-text-secondary)", marginTop: 4 }}>
                Laisser vide pour utiliser la valeur du fichier .env
              </p>
            </Field>
            <Field label="Modèle Groq">
              <select className="ods-select" value={app.groq_model}
                onChange={(e) => setAppField("groq_model", e.target.value)}>
                {GROQ_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </Field>
          </FieldRow>
          <FieldRow>
            <Field label="Clé API Anthropic (optionnel, fallback)">
              <input className="ods-input" type="password" placeholder="sk-ant-…"
                value={app.anthropic_api_key}
                onChange={(e) => setAppField("anthropic_api_key", e.target.value)} />
              <p style={{ fontSize: 11, color: "var(--ods-text-secondary)", marginTop: 4 }}>
                Utilisé si Groq est indisponible. Laisser vide pour désactiver.
              </p>
            </Field>
          </FieldRow>
        </Section>

        {/* ── Section 2 : Domaines ─────────────────────────────────── */}
        <Section title="🏢 Domaines métier">
          <div style={{ marginBottom: 24 }}>
            <label className="ods-label" style={{ marginBottom: 10, display: "block" }}>
              Domaines actifs
            </label>
            <TagList items={app.domain_list} onRemove={handleDomainTag}
              placeholder="Nouveau domaine (ex: energie)…" />
          </div>

          <div>
            <label className="ods-label" style={{ marginBottom: 10, display: "block" }}>
              Groupes de similarité
            </label>
            <p style={{ fontSize: 13, color: "var(--ods-text-secondary)", marginBottom: 14 }}>
              Définissez les domaines considérés comme proches. Le matching privilégiera les consultants ayant de l'expérience dans un domaine similaire.
            </p>

            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 16 }}>
              {app.domain_list.map((d) => (
                <button key={d} type="button"
                  onClick={() => setSimDomain(simDomain === d ? "" : d)}
                  style={{
                    padding: "6px 14px", borderRadius: 20, fontSize: 13, cursor: "pointer",
                    border: simDomain === d ? "2px solid #FF7900" : "1px solid var(--ods-border)",
                    background: simDomain === d ? "#fff5ec" : "var(--ods-surface)",
                    color: simDomain === d ? "#FF7900" : "var(--ods-text-primary)",
                    fontWeight: simDomain === d ? 500 : 400,
                  }}>
                  {d}
                  {(app.domain_similar[d] ?? []).length > 0 && (
                    <span style={{ marginLeft: 6, fontSize: 11, opacity: 0.7 }}>
                      ↔ {(app.domain_similar[d] ?? []).join(", ")}
                    </span>
                  )}
                </button>
              ))}
            </div>

            {simDomain && (
              <div style={{ padding: 16, background: "#fffdf5", border: "1px solid #f59e0b", borderRadius: 8 }}>
                <p style={{ fontSize: 13, fontWeight: 500, marginBottom: 12 }}>
                  Domaines similaires à <strong>{simDomain}</strong> :
                </p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
                  {app.domain_list.filter((d) => d !== simDomain).map((d) => {
                    const active = (app.domain_similar[simDomain] ?? []).includes(d);
                    return (
                      <button key={d} type="button"
                        onClick={() => handleSimilarTag(simDomain, active ? d : `__add__${d}`)}
                        style={{
                          padding: "4px 12px", borderRadius: 4, fontSize: 13, cursor: "pointer",
                          border: active ? "1px solid var(--ods-success)" : "1px solid var(--ods-border)",
                          background: active ? "#f0fdf4" : "#fff",
                          color: active ? "var(--ods-success)" : "var(--ods-text-primary)",
                          fontWeight: active ? 500 : 400,
                        }}>
                        {active ? "✓ " : "+ "}{d}
                      </button>
                    );
                  })}
                </div>
                <p style={{ fontSize: 11, color: "var(--ods-text-secondary)" }}>
                  Cliquez pour activer/désactiver. Vous pouvez aussi taper un domaine personnalisé :
                </p>
                <CustomSimInput onAdd={(d) => handleSimilarTag(simDomain, `__add__${d}`)} />
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
                  {(app.domain_similar[simDomain] ?? [])
                    .filter((d) => !app.domain_list.includes(d))
                    .map((d) => (
                      <span key={d} onClick={() => handleSimilarTag(simDomain, d)}
                        style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12,
                          background: "#e8f0fe", color: "#0055aa", borderRadius: 20,
                          padding: "3px 10px", cursor: "pointer" }}>
                        {d} ×
                      </span>
                    ))}
                </div>
              </div>
            )}
          </div>
        </Section>

        {/* ── Section 3 : Email ────────────────────────────────────── */}
        <Section title="✉ Configuration email">
          <div style={{ marginBottom: 24 }}>
            <label className="ods-label" style={{ marginBottom: 10, display: "block" }}>
              Destinataires (pôle staffing)
            </label>
            <TagList items={email.recipients} onRemove={handleRecipientTag}
              placeholder="staffing@orange.com" />
          </div>

          <div style={{ height: 1, background: "var(--ods-border)", margin: "20px 0" }} />

          <p style={{ fontSize: 13, fontWeight: 500, marginBottom: 16, color: "var(--ods-text-secondary)" }}>
            Serveur SMTP
          </p>

          <FieldRow>
            <Field label="Hôte SMTP">
              <input className="ods-input" placeholder="smtp.gmail.com"
                value={email.smtp_host}
                onChange={(e) => setEmailField("smtp_host", e.target.value)} />
            </Field>
            <Field label="Port SMTP">
              <input className="ods-input" type="number" placeholder="587"
                value={email.smtp_port}
                onChange={(e) => setEmailField("smtp_port", Number(e.target.value))} />
            </Field>
          </FieldRow>

          <FieldRow>
            <Field label="Utilisateur SMTP">
              <input className="ods-input" placeholder="user@domaine.com"
                value={email.smtp_user}
                onChange={(e) => setEmailField("smtp_user", e.target.value)} />
            </Field>
            <Field label="Mot de passe SMTP">
              <input className="ods-input" type="password" placeholder="••••••••"
                value={email.smtp_password}
                onChange={(e) => setEmailField("smtp_password", e.target.value)} />
              <p style={{ fontSize: 11, color: "var(--ods-text-secondary)", marginTop: 4 }}>
                Laisser "***" pour conserver le mot de passe actuel
              </p>
            </Field>
          </FieldRow>

          <FieldRow>
            <Field label="Adresse d'expéditeur">
              <input className="ods-input" placeholder="matchconsult@orange.com"
                value={email.sender_email}
                onChange={(e) => setEmailField("sender_email", e.target.value)} />
            </Field>
            <Field label="Nom d'expéditeur">
              <input className="ods-input" placeholder="MatchConsult"
                value={email.sender_name}
                onChange={(e) => setEmailField("sender_name", e.target.value)} />
            </Field>
          </FieldRow>
        </Section>

        {/* Bouton bas de page */}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
          <button type="button" className="ods-btn-outline" onClick={load} disabled={loading || saving}>
            Annuler les modifications
          </button>
          <button type="button" className="ods-btn-primary" onClick={save}
            disabled={saving} style={{ minWidth: 160 }}>
            {saving ? "Enregistrement…" : "Enregistrer tout"}
          </button>
        </div>
      </div>
    </div>
  );
}
