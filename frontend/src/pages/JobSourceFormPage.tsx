import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { Spinner } from "../components/Spinner";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import {
  useCreateJobSource,
  useDeleteJobSource,
  useJobSource,
  useTestJobSource,
  useUpdateJobSource,
} from "../hooks/useJobSources";
import { extractApiError } from "../lib/apiError";
import { confirm } from "../lib/dialogs";
import { toast } from "../lib/toast";
import {
  isPlaywrightAdapter,
  JOB_ADAPTER_TYPES,
  type JobAdapterType,
  type JobSourceCreate,
  type JobSourceTestResult,
} from "../types/jobs";

interface FormState {
  name: string;
  isin: string;
  portal_url: string;
  adapter_type: JobAdapterType;
  adapter_settings_json: string;
  is_active: boolean;
}

const ADAPTER_TEMPLATES: Record<JobAdapterType, string> = {
  static_html: JSON.stringify(
    {
      count_selector: ".job-card",
      timeout_seconds: 20,
    },
    null,
    2
  ),
  static_text_regex: JSON.stringify(
    {
      regex_pattern: "(\\d[\\d,]*)\\s*result\\(s\\)",
      timeout_seconds: 20,
    },
    null,
    2
  ),
  json_get_path_int: JSON.stringify(
    {
      endpoint: "https://api.example.com/jobs",
      value_path: "meta.totalHits",
      params: {},
      headers: {},
      timeout_seconds: 20,
    },
    null,
    2
  ),
  json_get_array_count: JSON.stringify(
    {
      endpoint: "https://api.example.com/jobs",
      array_field: "jobs",
      params: {},
      headers: {},
      timeout_seconds: 20,
    },
    null,
    2
  ),
  json_post_path_int: JSON.stringify(
    {
      endpoint: "https://api.example.com/search",
      value_path: "total",
      payload: {},
      headers: { "content-type": "application/json" },
      timeout_seconds: 20,
    },
    null,
    2
  ),
  json_post_facet_sum: JSON.stringify(
    {
      endpoint: "https://api.example.com/facets",
      facet_field: "country",
      payload: {},
      headers: { "content-type": "application/json" },
      timeout_seconds: 20,
    },
    null,
    2
  ),
  playwright_api_fetch: JSON.stringify(
    {
      endpoint: "https://careers.example.com/api/jobs",
      value_path: "data.totalJob",
      method: "POST",
      payload: {},
      timeout_ms: 30000,
    },
    null,
    2
  ),
  playwright_css_count: JSON.stringify(
    {
      count_selector: ".job-card",
      wait_for_selector: ".results",
      timeout_ms: 30000,
    },
    null,
    2
  ),
  playwright_text_regex: JSON.stringify(
    {
      wait_for_selector: "h2",
      regex_pattern: "(\\d[\\d,]*)\\s*results?",
      timeout_ms: 45000,
    },
    null,
    2
  ),
};

const ADAPTER_HINTS: Record<JobAdapterType, string> = {
  static_html: "GET HTML, BeautifulSoup-Selector zählt passende Elemente.",
  static_text_regex:
    "GET HTML, integer per Regex aus dem Response-Text extrahieren (kein Browser).",
  json_get_path_int:
    "GET JSON, integer am dotted path lesen (z.B. 'meta.totalHits').",
  json_get_array_count:
    "GET JSON, Array-Feld zählen (z.B. 'jobs' → length).",
  json_post_path_int:
    "POST JSON-Payload, integer am dotted path lesen.",
  json_post_facet_sum:
    "POST JSON-Payload, Counts in facets.map.<facet_field> summieren.",
  playwright_api_fetch:
    "Playwright öffnet das Portal (für Cookies/Cloudflare), dann fetch() der API aus dem Browser-Context.",
  playwright_css_count:
    "Playwright rendert die Seite, zählt DOM-Elemente per CSS-Selector.",
  playwright_text_regex:
    "Playwright rendert die Seite, sucht den Counter per Regex im sichtbaren Text.",
};

function emptyState(adapter: JobAdapterType, isin: string | null): FormState {
  return {
    name: "",
    isin: isin ?? "",
    portal_url: "",
    adapter_type: adapter,
    adapter_settings_json: ADAPTER_TEMPLATES[adapter],
    is_active: true,
  };
}

export function JobSourceFormPage() {
  const { id } = useParams<{ id?: string }>();
  const isNew = id === "new" || id == null;
  const sourceId = isNew ? undefined : Number(id);
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  useDocumentTitle(isNew ? "Neue Job-Quelle" : "Job-Quelle bearbeiten");

  const sourceQuery = useJobSource(sourceId);
  const createMutation = useCreateJobSource();
  const updateMutation = useUpdateJobSource(sourceId ?? 0);
  const deleteMutation = useDeleteJobSource();
  const testMutation = useTestJobSource();

  const [state, setState] = useState<FormState>(() =>
    emptyState("json_get_path_int", searchParams.get("isin"))
  );
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<JobSourceTestResult | null>(null);

  useEffect(() => {
    if (!isNew && sourceQuery.data) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setState({
        name: sourceQuery.data.name,
        isin: sourceQuery.data.isin ?? "",
        portal_url: sourceQuery.data.portal_url,
        adapter_type: sourceQuery.data.adapter_type,
        adapter_settings_json: JSON.stringify(
          sourceQuery.data.adapter_settings ?? {},
          null,
          2
        ),
        is_active: sourceQuery.data.is_active,
      });
    }
  }, [isNew, sourceQuery.data]);

  const adapterHint = useMemo(
    () => ADAPTER_HINTS[state.adapter_type],
    [state.adapter_type]
  );

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setState((prev) => ({ ...prev, [key]: value }));
  }

  function changeAdapter(next: JobAdapterType) {
    setState((prev) => ({
      ...prev,
      adapter_type: next,
      adapter_settings_json: ADAPTER_TEMPLATES[next],
    }));
    setJsonError(null);
    setTestResult(null);
  }

  function parseSettings(): Record<string, unknown> | null {
    try {
      const parsed = JSON.parse(state.adapter_settings_json);
      if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
        setJsonError("Adapter-Settings müssen ein JSON-Objekt sein.");
        return null;
      }
      setJsonError(null);
      return parsed as Record<string, unknown>;
    } catch (err) {
      setJsonError(
        err instanceof Error ? `Ungültiges JSON: ${err.message}` : "Ungültiges JSON."
      );
      return null;
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const settings = parseSettings();
    if (settings === null) return;

    const payload: JobSourceCreate = {
      name: state.name.trim(),
      isin: state.isin.trim() ? state.isin.trim().toUpperCase() : null,
      portal_url: state.portal_url.trim(),
      adapter_type: state.adapter_type,
      adapter_settings: settings,
      is_active: state.is_active,
    };

    try {
      if (isNew) {
        const created = await createMutation.mutateAsync(payload);
        toast.success(`${created.name} angelegt.`);
        navigate(`/jobs/${created.id}`);
      } else {
        await updateMutation.mutateAsync(payload);
        toast.success("Quelle aktualisiert.");
      }
    } catch (err) {
      toast.error(extractApiError(err, "Speichern fehlgeschlagen."));
    }
  }

  async function handleTest() {
    if (isNew || sourceId == null) {
      toast.info("Bitte zuerst speichern, dann testen.");
      return;
    }
    // Make sure the unsaved settings are persisted first so the backend test
    // hits the configuration the user is currently editing.
    const settings = parseSettings();
    if (settings === null) return;
    try {
      await updateMutation.mutateAsync({
        name: state.name,
        isin: state.isin ? state.isin.toUpperCase() : null,
        portal_url: state.portal_url,
        adapter_type: state.adapter_type,
        adapter_settings: settings,
        is_active: state.is_active,
      });
      const result = await testMutation.mutateAsync(sourceId);
      setTestResult(result);
    } catch (err) {
      toast.error(extractApiError(err, "Test fehlgeschlagen."));
    }
  }

  async function handleDelete() {
    if (!sourceId) return;
    const ok = await confirm({
      title: "Quelle löschen",
      message: `${state.name} wirklich löschen? Snapshots werden mitgelöscht.`,
      destructive: true,
      confirmLabel: "Löschen",
    });
    if (!ok) return;
    try {
      await deleteMutation.mutateAsync(sourceId);
      toast.success("Quelle gelöscht.");
      navigate("/jobs");
    } catch (err) {
      toast.error(extractApiError(err, "Löschen fehlgeschlagen."));
    }
  }

  if (!isNew && sourceQuery.isLoading) {
    return (
      <div className="page">
        <Spinner label="Lade Quelle…" />
      </div>
    );
  }

  if (!isNew && sourceQuery.isError) {
    return (
      <div className="page">
        <p className="form-banner-error">
          {extractApiError(sourceQuery.error, "Quelle konnte nicht geladen werden.")}
        </p>
      </div>
    );
  }

  return (
    <div className="page">
      <header className="page-header">
        <div className="page-header-title">
          <h2>{isNew ? "Neue Karriereportal-Quelle" : `Quelle bearbeiten: ${state.name}`}</h2>
        </div>
        <div className="page-header-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={() => navigate("/jobs")}
          >
            Zurück
          </button>
        </div>
      </header>

      <form onSubmit={handleSubmit} className="job-source-form">
        <label>
          Name
          <input
            type="text"
            value={state.name}
            onChange={(e) => update("name", e.target.value)}
            required
            maxLength={128}
          />
        </label>

        <label>
          Portal-URL
          <input
            type="url"
            value={state.portal_url}
            onChange={(e) => update("portal_url", e.target.value)}
            placeholder="https://careers.example.com"
            required
          />
        </label>

        <label>
          ISIN (optional, verknüpft mit Watchlist-Eintrag)
          <input
            type="text"
            value={state.isin}
            onChange={(e) => update("isin", e.target.value.toUpperCase())}
            maxLength={12}
            placeholder="DE0007100000"
          />
        </label>

        <label>
          Adapter-Typ
          <select
            value={state.adapter_type}
            onChange={(e) => changeAdapter(e.target.value as JobAdapterType)}
          >
            {JOB_ADAPTER_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
                {isPlaywrightAdapter(t) ? " (Playwright)" : ""}
              </option>
            ))}
          </select>
          <span className="form-hint">{adapterHint}</span>
          {isPlaywrightAdapter(state.adapter_type) && (
            <span className="form-hint form-hint-warn">
              Erfordert das Playwright-Extra:
              {" "}<code>pip install -e .[playwright]</code> +
              {" "}<code>python -m playwright install chromium</code>
            </span>
          )}
        </label>

        <label>
          Adapter-Settings (JSON)
          <textarea
            value={state.adapter_settings_json}
            onChange={(e) => update("adapter_settings_json", e.target.value)}
            spellCheck={false}
          />
          {jsonError && <span className="form-error-text">{jsonError}</span>}
        </label>

        <label className="form-checkbox">
          <input
            type="checkbox"
            checked={state.is_active}
            onChange={(e) => update("is_active", e.target.checked)}
          />
          Aktiv (im Cron + bei &quot;Alle aktualisieren&quot; einbeziehen)
        </label>

        {testResult && (
          <div className="job-source-form-test-result">
            <strong>Test-Ergebnis:</strong> {testResult.status}
            {testResult.status === "ok" && (
              <>
                {" · "}Aktuell offen: <strong>{testResult.jobs_count}</strong>
                {" · "}Dauer: {testResult.duration_ms} ms
              </>
            )}
            {testResult.status === "error" && (
              <>
                {" · "}Fehler: {testResult.error}
              </>
            )}
          </div>
        )}

        <div className="job-source-form-actions">
          {!isNew && (
            <button
              type="button"
              className="btn-danger"
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
            >
              Löschen
            </button>
          )}
          {!isNew && (
            <button
              type="button"
              className="btn-secondary"
              onClick={handleTest}
              disabled={testMutation.isPending || updateMutation.isPending}
              title="Speichert Änderungen und testet die Konfiguration live."
            >
              {testMutation.isPending ? "Teste…" : "Speichern + Testen"}
            </button>
          )}
          <button
            type="submit"
            className="btn-primary"
            disabled={
              createMutation.isPending ||
              updateMutation.isPending ||
              !state.name.trim() ||
              !state.portal_url.trim()
            }
          >
            {createMutation.isPending || updateMutation.isPending
              ? "Speichere…"
              : isNew
              ? "Anlegen"
              : "Speichern"}
          </button>
        </div>
      </form>
    </div>
  );
}

export default JobSourceFormPage;
