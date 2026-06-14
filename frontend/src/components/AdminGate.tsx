import React, { useState } from "react";

const ADMIN_PIN = "matchconsult";

interface Props {
  onUnlock: () => void;
  onCancel: () => void;
}

export function AdminGate({ onUnlock, onCancel }: Props) {
  const [value, setValue] = useState("");
  const [error, setError] = useState(false);

  const submit = () => {
    if (value === ADMIN_PIN) {
      onUnlock();
    } else {
      setError(true);
      setValue("");
    }
  };

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 200,
    }}>
      <div className="ods-card" style={{ width: 360, padding: 32 }}>
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 20, fontWeight: 600, marginBottom: 6 }}>
            🔒 Accès Administration
          </div>
          <p style={{ fontSize: 13, color: "var(--ods-text-secondary)" }}>
            Cette section est réservée aux administrateurs. Entrez le code d'accès.
          </p>
        </div>

        <input
          className="ods-input"
          type="password"
          placeholder="Code d'accès"
          value={value}
          autoFocus
          onChange={(e) => { setValue(e.target.value); setError(false); }}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          style={{ marginBottom: error ? 6 : 16 }}
        />

        {error && (
          <p style={{ fontSize: 12, color: "var(--ods-error)", marginBottom: 14 }}>
            Code incorrect. Réessayez.
          </p>
        )}

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button type="button" className="ods-btn-outline" onClick={onCancel}>
            Annuler
          </button>
          <button type="button" className="ods-btn-primary" onClick={submit}>
            Accéder
          </button>
        </div>
      </div>
    </div>
  );
}
