import { useEffect, useState } from "react";

import { api } from "../api/client";
import { Spinner } from "../components/Spinner";
import { ColorThresholds, defaultThresholds } from "../lib/colorRules";
import { extractApiError } from "../lib/apiError";

interface SettingsState {
  update_hour: number;
  update_minute: number;
  update_weekends: boolean;
  ai_provider: string;
  ai_endpoint: string | null;
  ai_model: string;
  ai_refresh_interval: string;
  // Other backend fields are kept on `extra` so they survive a round-trip.
  [key: string]: unknown;
}

export function SettingsPage() {
  const [settings, setSettings] = useState<SettingsState | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [thresholds, setThresholds] = useState<ColorThresholds>(defaultThresholds);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  useEffect(() => {
    api
      .get("/settings")
      .then((res) => setSettings(res.data))
      .catch((err) =>
        setFeedback({ kind: "error", text: extractApiError(err, "Einstellungen konnten nicht geladen werden.") })
      );
    const raw = localStorage.getItem("ct-thresholds");
    if (raw) {
      try {
        setThresholds({ ...defaultThresholds, ...JSON.parse(raw) });
      } catch {
        setThresholds(defaultThresholds);
      }
    }
  }, []);

  async function save() {
    if (!settings) return;
    setSaving(true);
    setFeedback(null);
    try {
      await api.put("/settings", { ...settings, ai_api_key: apiKey || undefined });
      localStorage.setItem("ct-thresholds", JSON.stringify(thresholds));
      setApiKey("");
      setFeedback({ kind: "ok", text: "Gespeichert." });
    } catch (err) {
      setFeedback({ kind: "error", text: extractApiError(err, "Speichern fehlgeschlagen.") });
    } finally {
      setSaving(false);
    }
  }

  if (!settings) {
    return (
      <div className="page">
        <Spinner label="Lade Einstellungen..." />
      </div>
    );
  }
  return (
    <div className="page">
      <h2>Einstellungen</h2>
      <input
        type="number"
        value={settings.update_hour}
        onChange={(e) => setSettings({ ...settings, update_hour: Number(e.target.value) })}
      />
      <input
        type="number"
        value={settings.update_minute}
        onChange={(e) => setSettings({ ...settings, update_minute: Number(e.target.value) })}
      />
      <label>
        <input
          type="checkbox"
          checked={settings.update_weekends}
          onChange={(e) => setSettings({ ...settings, update_weekends: e.target.checked })}
        />
        Update am Wochenende
      </label>
      <input
        value={settings.ai_provider}
        onChange={(e) => setSettings({ ...settings, ai_provider: e.target.value })}
        placeholder="openai / ollama"
      />
      <input
        value={settings.ai_endpoint || ""}
        onChange={(e) => setSettings({ ...settings, ai_endpoint: e.target.value })}
        placeholder="AI Endpoint"
      />
      <input value={settings.ai_model} onChange={(e) => setSettings({ ...settings, ai_model: e.target.value })} />
      <input
        value={settings.ai_refresh_interval}
        onChange={(e) => setSettings({ ...settings, ai_refresh_interval: e.target.value })}
        placeholder="daily/weekly/monthly/manual"
      />
      <input value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="AI API Key (optional neu)" />
      <h3>Farb-Schwellen (lokal)</h3>
      <input
        type="number"
        value={thresholds.strongGainPct}
        onChange={(e) => setThresholds({ ...thresholds, strongGainPct: Number(e.target.value) })}
        placeholder="Gewinn %"
      />
      <input
        type="number"
        value={thresholds.strongLossPct}
        onChange={(e) => setThresholds({ ...thresholds, strongLossPct: Number(e.target.value) })}
        placeholder="Verlust %"
      />
      <input
        type="number"
        value={thresholds.targetDistancePct}
        onChange={(e) => setThresholds({ ...thresholds, targetDistancePct: Number(e.target.value) })}
        placeholder="Kursziel Abstand %"
      />
      <input
        type="number"
        value={thresholds.highDividendPct}
        onChange={(e) => setThresholds({ ...thresholds, highDividendPct: Number(e.target.value) })}
        placeholder="Dividende %"
      />
      <button type="button" className="btn-primary" onClick={save} disabled={saving}>
        {saving ? "Speichere..." : "Speichern"}
      </button>
      {feedback && (
        <p className={feedback.kind === "ok" ? "form-banner-ok" : "form-banner-error"} role="alert">
          {feedback.text}
        </p>
      )}
    </div>
  );
}
