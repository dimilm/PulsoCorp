import { SettingsState, TestResult } from "../../hooks/useSettings";

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

interface Props {
  settings: SettingsState;
  onChange: (patch: Partial<SettingsState>) => void;
  apiKey: string;
  setApiKey: (value: string) => void;
  editKey: boolean;
  setEditKey: (value: boolean) => void;
  testing: boolean;
  testResult: TestResult | null;
  setTestResult: (result: TestResult | null) => void;
  isDirty: boolean;
  onTestConnection: () => void;
}

export function AiProviderCard({
  settings,
  onChange,
  apiKey,
  setApiKey,
  editKey,
  setEditKey,
  testing,
  testResult,
  setTestResult,
  isDirty,
  onTestConnection,
}: Props) {
  const providerPresets = MODEL_PRESETS[settings.ai_provider] ?? [];
  const isOllama = settings.ai_provider === "ollama";

  function handleProviderChange(nextProvider: string) {
    const presets = MODEL_PRESETS[nextProvider] ?? [];
    const nextModel =
      presets.length > 0 ? presets[0] : (DEFAULT_MODEL[nextProvider] ?? settings.ai_model);
    onChange({ ai_provider: nextProvider, ai_endpoint: "", ai_model: nextModel });
    setTestResult(null);
  }

  return (
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
          onChange={(e) => handleProviderChange(e.target.value)}
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
            onChange={(e) => onChange({ ai_model: e.target.value })}
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
            onChange={(e) => onChange({ ai_model: e.target.value })}
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
            <button type="button" className="btn-secondary" onClick={() => setEditKey(true)}>
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
                    onClick={() => {
                      setEditKey(false);
                      setApiKey("");
                    }}
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
          onChange={(e) => onChange({ ai_refresh_interval: e.target.value })}
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
          onClick={onTestConnection}
          disabled={testing || (isDirty && !settings.ai_api_key_set && !apiKey)}
          title={
            isDirty
              ? "Erst speichern, dann testet der Button die hinterlegte Konfiguration."
              : undefined
          }
        >
          {testing ? "Teste..." : "Verbindung testen"}
        </button>
        {testResult && testResult.ok && (
          <span className="settings-status-ok">OK · {testResult.latency_ms} ms</span>
        )}
        {testResult && !testResult.ok && (
          <span className="settings-status-error">Fehler: {testResult.error}</span>
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
              onChange={(e) => onChange({ ai_endpoint: e.target.value })}
              placeholder="https://api.openai.com/v1/chat/completions"
            />
            <span className="helper">
              Leer lassen für den Standard-Endpoint des gewählten Anbieters.
            </span>
          </div>
        </div>
      </details>
    </section>
  );
}
