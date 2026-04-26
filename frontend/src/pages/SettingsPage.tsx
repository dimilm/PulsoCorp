import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { Spinner } from "../components/Spinner";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { extractApiError } from "../lib/apiError";
import { ColorThresholds, defaultThresholds } from "../lib/colorRules";

interface SettingsState {
  update_hour: number;
  update_minute: number;
  update_weekends: boolean;
  ai_provider: string;
  ai_endpoint: string | null;
  ai_model: string;
  ai_refresh_interval: string;
  ai_api_key_set: boolean;
}

interface TestResult {
  ok: boolean;
  latency_ms?: number;
  error?: string;
  provider?: string;
  model?: string;
}

const AI_PROVIDERS = [
  { value: "openai", label: "OpenAI" },
  { value: "gemini", label: "Google Gemini" },
  { value: "ollama", label: "Ollama (lokal)" },
] as const;

const MODEL_PRESETS: Record<string, string[]> = {
  openai: ["gpt-4o-mini", "gpt-4o"],
  gemini: ["gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
  ollama: [],
};

const DEFAULT_MODEL: Record<string, string> = {
  openai: "gpt-4o-mini",
  gemini: "gemini-3-flash-preview",
  ollama: "llama3",
};

const REFRESH_INTERVAL_OPTIONS = [
  { value: "daily", label: "Täglich (höhere KI-Kosten)" },
  { value: "weekly", label: "Wöchentlich" },
  { value: "monthly", label: "Monatlich (empfohlen)" },
  { value: "manual", label: "Nur manuell" },
] as const;

function pad2(n: number): string {
  return n.toString().padStart(2, "0");
}

function timeToString(hour: number, minute: number): string {
  return `${pad2(hour)}:${pad2(minute)}`;
}

function parseTime(value: string): { hour: number; minute: number } | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(value);
  if (!match) return null;
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (Number.isNaN(hour) || Number.isNaN(minute)) return null;
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return null;
  return { hour, minute };
}

export function SettingsPage() {
  useDocumentTitle("Einstellungen");
  const [settings, setSettings] = useState<SettingsState | null>(null);
  const [initialSettings, setInitialSettings] = useState<SettingsState | null>(null);
  const [thresholds, setThresholds] = useState<ColorThresholds>(defaultThresholds);
  const [initialThresholds, setInitialThresholds] = useState<ColorThresholds>(defaultThresholds);
  const [editKey, setEditKey] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [exportingSeed, setExportingSeed] = useState(false);
  const [exportingCsv, setExportingCsv] = useState(false);
  const [feedback, setFeedback] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get("/settings")
      .then((res) => {
        const data = res.data as SettingsState;
        setSettings(data);
        setInitialSettings(data);
      })
      .catch((err) =>
        setLoadError(extractApiError(err, "Einstellungen konnten nicht geladen werden."))
      );
    const raw = localStorage.getItem("ct-thresholds");
    if (raw) {
      try {
        const merged = { ...defaultThresholds, ...JSON.parse(raw) };
        setThresholds(merged);
        setInitialThresholds(merged);
      } catch {
        setThresholds(defaultThresholds);
        setInitialThresholds(defaultThresholds);
      }
    }
  }, []);

  const isDirty = useMemo(() => {
    if (!settings || !initialSettings) return false;
    if (apiKey.trim()) return true;
    if (JSON.stringify(settings) !== JSON.stringify(initialSettings)) return true;
    if (JSON.stringify(thresholds) !== JSON.stringify(initialThresholds)) return true;
    return false;
  }, [settings, initialSettings, editKey, apiKey, thresholds, initialThresholds]);

  async function save() {
    if (!settings) return;
    setSaving(true);
    setFeedback(null);
    try {
      const payload: Record<string, unknown> = {
        update_hour: settings.update_hour,
        update_minute: settings.update_minute,
        update_weekends: settings.update_weekends,
        ai_provider: settings.ai_provider,
        ai_endpoint: settings.ai_endpoint,
        ai_model: settings.ai_model,
        ai_refresh_interval: settings.ai_refresh_interval,
      };
      if (apiKey.trim()) {
        payload.ai_api_key = apiKey.trim();
      }
      const res = await api.put("/settings", payload);
      const fresh = res.data as SettingsState;
      setSettings(fresh);
      setInitialSettings(fresh);
      localStorage.setItem("ct-thresholds", JSON.stringify(thresholds));
      setInitialThresholds(thresholds);
      setApiKey("");
      setEditKey(false);
      setFeedback({ kind: "ok", text: "Einstellungen gespeichert." });
    } catch (err) {
      setFeedback({ kind: "error", text: extractApiError(err, "Speichern fehlgeschlagen.") });
    } finally {
      setSaving(false);
    }
  }

  function discardChanges() {
    if (initialSettings) setSettings(initialSettings);
    setThresholds(initialThresholds);
    setApiKey("");
    setEditKey(false);
    setFeedback(null);
    setTestResult(null);
  }

  async function testConnection() {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await api.post("/ai/test");
      setTestResult(res.data as TestResult);
    } catch (err) {
      setTestResult({ ok: false, error: extractApiError(err, "Test fehlgeschlagen.") });
    } finally {
      setTesting(false);
    }
  }

  async function downloadBlob(url: string, filename: string, mediaType: string) {
    const res = await api.get(url, { responseType: "blob" });
    const blob = res.data instanceof Blob ? res.data : new Blob([res.data], { type: mediaType });
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(objectUrl);
  }

  async function downloadSeed() {
    setExportingSeed(true);
    setFeedback(null);
    try {
      await downloadBlob("/export/seed-json", "stocks.seed.json", "application/json");
      setFeedback({ kind: "ok", text: "Seed exportiert." });
    } catch (err) {
      setFeedback({ kind: "error", text: extractApiError(err, "Seed-Export fehlgeschlagen.") });
    } finally {
      setExportingSeed(false);
    }
  }

  async function downloadCsv() {
    setExportingCsv(true);
    setFeedback(null);
    try {
      await downloadBlob("/export/csv", "watchlist.csv", "text/csv");
      setFeedback({ kind: "ok", text: "Watchlist als CSV exportiert." });
    } catch (err) {
      setFeedback({ kind: "error", text: extractApiError(err, "CSV-Export fehlgeschlagen.") });
    } finally {
      setExportingCsv(false);
    }
  }

  if (loadError) {
    return (
      <div className="page">
        <p className="form-banner-error" role="alert">{loadError}</p>
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="page">
        <Spinner label="Lade Einstellungen..." />
      </div>
    );
  }

  const providerPresets = MODEL_PRESETS[settings.ai_provider] ?? [];
  const isOllama = settings.ai_provider === "ollama";
  const nextRunLabel = `${pad2(settings.update_hour)}:${pad2(settings.update_minute)}${
    settings.update_weekends ? "" : " (an Werktagen)"
  }`;

  return (
    <div className="page settings-page">
      <div className="page-header">
        <div className="page-header-title">
          <h2>Einstellungen</h2>
        </div>
      </div>

      <div className="settings-grid">
        {/* Karte 1: Automatisches Update ----------------------------------- */}
        <section className="settings-card">
          <header className="settings-card-header">
            <h3>Automatisches Update</h3>
            <p className="settings-card-subtitle">
              Wann werden Kurse, Kennzahlen und KI-Bewertungen für alle Aktien automatisch aktualisiert?
            </p>
          </header>

          <div className="field">
            <label htmlFor="setting-time">Lauf-Uhrzeit</label>
            <input
              id="setting-time"
              type="time"
              value={timeToString(settings.update_hour, settings.update_minute)}
              onChange={(e) => {
                const parsed = parseTime(e.target.value);
                if (parsed) {
                  setSettings({ ...settings, update_hour: parsed.hour, update_minute: parsed.minute });
                }
              }}
            />
            <span className="helper">
              Standard 22:30 (lokale Zeit), nach US-Börsenschluss. Lauf-Historie unter{" "}
              <Link to="/runs" className="settings-info-link">Läufe</Link>.
            </span>
          </div>

          <label className="toggle-row">
            <input
              type="checkbox"
              checked={settings.update_weekends}
              onChange={(e) => setSettings({ ...settings, update_weekends: e.target.checked })}
            />
            <span className="toggle-switch" aria-hidden="true">
              <span className="toggle-knob" />
            </span>
            <span className="toggle-text">
              <span className="toggle-title">Auch am Wochenende laufen</span>
              <span className="toggle-help">
                Standardmäßig aus, weil die Börsen am Wochenende geschlossen sind.
              </span>
            </span>
          </label>

          <div className="settings-info-line">
            <span>
              Nächster geplanter Lauf: <strong>{nextRunLabel}</strong>
            </span>
            <Link to="/runs" className="settings-info-link">→ Lauf-Historie öffnen</Link>
          </div>
        </section>

        {/* Karte 2: KI-Bewertung ------------------------------------------ */}
        <section className="settings-card">
          <header className="settings-card-header">
            <h3>KI-Bewertung</h3>
            <p className="settings-card-subtitle">
              Welcher Anbieter bewertet die Aktien (Fundamental-Score, DCF, Burggraben, Empfehlung)?
            </p>
          </header>

          <div className="field">
            <label htmlFor="setting-provider">KI-Anbieter</label>
            <select
              id="setting-provider"
              value={settings.ai_provider}
              onChange={(e) => {
                const nextProvider = e.target.value;
                const presets = MODEL_PRESETS[nextProvider] ?? [];
                const nextModel = presets.length > 0 ? presets[0] : DEFAULT_MODEL[nextProvider] ?? settings.ai_model;
                setSettings({
                  ...settings,
                  ai_provider: nextProvider,
                  ai_endpoint: "",
                  ai_model: nextModel,
                });
                setTestResult(null);
              }}
            >
              {AI_PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="setting-model">Modell</label>
            {providerPresets.length > 0 ? (
              <select
                id="setting-model"
                value={settings.ai_model}
                onChange={(e) => setSettings({ ...settings, ai_model: e.target.value })}
              >
                {providerPresets.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
                {!providerPresets.includes(settings.ai_model) && (
                  <option value={settings.ai_model}>{settings.ai_model} (eigenes)</option>
                )}
              </select>
            ) : (
              <input
                id="setting-model"
                value={settings.ai_model}
                onChange={(e) => setSettings({ ...settings, ai_model: e.target.value })}
                placeholder="z. B. llama3"
              />
            )}
          </div>

          <div className="field">
            <label htmlFor="setting-api-key">API-Schlüssel</label>
            {isOllama ? (
              <div className="settings-key-disabled">
                Lokales Modell — kein API-Schlüssel nötig.
              </div>
            ) : settings.ai_api_key_set && !editKey ? (
              <div className="settings-key-row">
                <span className="settings-key-pill">Schlüssel hinterlegt</span>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setEditKey(true)}
                >
                  Schlüssel ändern
                </button>
              </div>
            ) : (
              <>
                <input
                  id="setting-api-key"
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={settings.ai_api_key_set ? "Neuen Schlüssel eingeben" : "Schlüssel einfügen"}
                  autoComplete="off"
                />
                <span className="helper">
                  Wird verschlüsselt in der Datenbank gespeichert.
                  {settings.ai_api_key_set && editKey && (
                    <>
                      {" "}
                      <button
                        type="button"
                        className="btn-link"
                        onClick={() => { setEditKey(false); setApiKey(""); }}
                      >
                        Abbrechen
                      </button>
                    </>
                  )}
                </span>
              </>
            )}
          </div>

          <div className="field">
            <label htmlFor="setting-interval">KI-Refresh-Intervall</label>
            <select
              id="setting-interval"
              value={settings.ai_refresh_interval}
              onChange={(e) => setSettings({ ...settings, ai_refresh_interval: e.target.value })}
            >
              {REFRESH_INTERVAL_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <span className="helper">
              Wie oft soll die KI eine Aktie neu bewerten? DCF/NAV/Burggraben ändern sich selten.
            </span>
          </div>

          <div className="settings-test-row">
            <button
              type="button"
              className="btn-secondary"
              onClick={testConnection}
              disabled={testing || (isDirty && !settings.ai_api_key_set && !apiKey)}
              title={isDirty ? "Erst speichern, dann testet der Button die hinterlegte Konfiguration." : undefined}
            >
              {testing ? "Teste..." : "Verbindung testen"}
            </button>
            {testResult && testResult.ok && (
              <span className="settings-status-ok">
                OK · {testResult.latency_ms} ms
              </span>
            )}
            {testResult && !testResult.ok && (
              <span className="settings-status-error">
                Fehler: {testResult.error}
              </span>
            )}
          </div>

          <details className="settings-advanced">
            <summary>Erweiterte Einstellungen</summary>
            <div className="settings-advanced-body">
              <div className="field">
                <label htmlFor="setting-endpoint">Eigener Endpoint</label>
                <input
                  id="setting-endpoint"
                  value={settings.ai_endpoint || ""}
                  onChange={(e) => setSettings({ ...settings, ai_endpoint: e.target.value })}
                  placeholder="https://api.openai.com/v1/chat/completions"
                />
                <span className="helper">
                  Leer lassen für den Standard-Endpoint des gewählten Anbieters.
                </span>
              </div>
            </div>
          </details>
        </section>

        {/* Karte 3: Daten exportieren ------------------------------------- */}
        <section className="settings-card">
          <header className="settings-card-header">
            <h3>Daten exportieren</h3>
            <p className="settings-card-subtitle">
              Watchlist als CSV für Excel oder als Seed-Datei für Source/Backup herunterladen.
            </p>
          </header>

          <div className="settings-export-row">
            <span className="settings-export-title">Watchlist als CSV</span>
            <span className="helper">
              Aktuelle Aktien mit Kurs, Empfehlung und investiertem Kapital — direkt in Excel öffnen.
            </span>
            <div className="settings-export-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={downloadCsv}
                disabled={exportingCsv}
              >
                {exportingCsv ? "Exportiere..." : "CSV herunterladen"}
              </button>
            </div>
          </div>

          <div className="settings-export-row">
            <span className="settings-export-title">Seed-Datei (stocks.seed.json)</span>
            <span className="helper">
              Lädt den aktuellen DB-Stand als <code>stocks.seed.json</code> herunter. Datei in{" "}
              <code>backend/app/seed/</code> ablegen, um den Seed im Source zu aktualisieren.
            </span>
            <div className="settings-export-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={downloadSeed}
                disabled={exportingSeed}
              >
                {exportingSeed ? "Exportiere..." : "Seed herunterladen"}
              </button>
            </div>
          </div>
        </section>

        {/* Karte 4: Farb-Schwellen ---------------------------------------- */}
        <section className="settings-card">
          <header className="settings-card-header">
            <h3>Farb-Schwellen</h3>
            <p className="settings-card-subtitle">
              Ab welchen Werten Tabellen-Spalten farbig hervorgehoben werden. Nur in deinem Browser gespeichert.
            </p>
          </header>

          <div className="field">
            <label htmlFor="th-gain">Tagesgewinn — ab welchem % wird die Spalte grün?</label>
            <input
              id="th-gain"
              type="number"
              step="0.1"
              value={thresholds.strongGainPct}
              onChange={(e) => setThresholds({ ...thresholds, strongGainPct: Number(e.target.value) })}
            />
            <span className="helper">Standard: 4 (z. B. +4,5 % wird grün eingefärbt).</span>
          </div>

          <div className="field">
            <label htmlFor="th-loss">Tagesverlust — ab welchem % wird die Spalte rot?</label>
            <input
              id="th-loss"
              type="number"
              step="0.1"
              value={thresholds.strongLossPct}
              onChange={(e) => setThresholds({ ...thresholds, strongLossPct: Number(e.target.value) })}
            />
            <span className="helper">Standard: −4 (negative Zahl). Werte unter dieser Schwelle werden rot.</span>
          </div>

          <div className="field">
            <label htmlFor="th-target">Analysten-Kursziel — ab wie viel % über Kurs türkis?</label>
            <input
              id="th-target"
              type="number"
              step="0.1"
              value={thresholds.targetDistancePct}
              onChange={(e) => setThresholds({ ...thresholds, targetDistancePct: Number(e.target.value) })}
            />
            <span className="helper">Standard: 10 (Kursziel ≥ 10 % über aktuellem Kurs).</span>
          </div>

          <div className="field">
            <label htmlFor="th-div">Hohe Dividendenrendite — ab welchem % türkis?</label>
            <input
              id="th-div"
              type="number"
              step="0.1"
              value={thresholds.highDividendPct}
              onChange={(e) => setThresholds({ ...thresholds, highDividendPct: Number(e.target.value) })}
            />
            <span className="helper">Standard: 4 (Dividendenrendite ≥ 4 %).</span>
          </div>

          <div className="settings-row">
            <button
              type="button"
              className="btn-link"
              onClick={() => setThresholds(defaultThresholds)}
            >
              Auf Standard zurücksetzen
            </button>
          </div>
        </section>
      </div>

      <footer className="settings-footer">
        {feedback ? (
          <p
            className={`settings-footer-status ${
              feedback.kind === "ok" ? "is-ok" : "is-error"
            }`}
            role="alert"
          >
            {feedback.text}
          </p>
        ) : (
          <p className="settings-footer-status">
            {isDirty ? "Du hast ungespeicherte Änderungen." : "Alle Änderungen gespeichert."}
          </p>
        )}
        <div className="settings-footer-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={discardChanges}
            disabled={!isDirty || saving}
          >
            Verwerfen
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={save}
            disabled={!isDirty || saving}
          >
            {saving ? "Speichere..." : "Speichern"}
          </button>
        </div>
      </footer>
    </div>
  );
}
