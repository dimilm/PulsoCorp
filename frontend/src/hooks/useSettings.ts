import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { ColorThresholds, defaultThresholds } from "../lib/colorRules";
import { extractApiError } from "../lib/apiError";

export interface SettingsState {
  update_hour: number;
  update_minute: number;
  update_weekends: boolean;
  ai_provider: string;
  ai_endpoint: string | null;
  ai_model: string;
  ai_refresh_interval: string;
  ai_api_key_set: boolean;
  jobs_enabled: boolean;
  jobs_update_hour: number;
  jobs_update_minute: number;
}

export interface TestResult {
  ok: boolean;
  latency_ms?: number;
  error?: string;
  provider?: string;
  model?: string;
}

export function useSettings() {
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
  const [exportingJobHistory, setExportingJobHistory] = useState(false);
  const [importingJobHistory, setImportingJobHistory] = useState(false);
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
        // eslint-disable-next-line react-hooks/set-state-in-effect
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
  }, [settings, initialSettings, apiKey, thresholds, initialThresholds]);

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
        jobs_enabled: settings.jobs_enabled,
        jobs_update_hour: settings.jobs_update_hour,
        jobs_update_minute: settings.jobs_update_minute,
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

  async function downloadJobHistory() {
    setExportingJobHistory(true);
    setFeedback(null);
    try {
      await downloadBlob("/job-sources/history/export-csv", "job-history.csv", "text/csv");
      setFeedback({ kind: "ok", text: "Job-Historie exportiert." });
    } catch (err) {
      setFeedback({ kind: "error", text: extractApiError(err, "Job-Historie-Export fehlgeschlagen.") });
    } finally {
      setExportingJobHistory(false);
    }
  }

  async function uploadJobHistory(file: File) {
    setImportingJobHistory(true);
    setFeedback(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await api.post("/job-sources/history/import-csv", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const report = res.data as {
        inserted: number;
        skipped_existing: number;
        unmapped_rows: unknown[];
        malformed_rows: unknown[];
        total_rows: number;
      };
      const parts: string[] = [];
      parts.push(`${report.inserted} eingefügt`);
      parts.push(`${report.skipped_existing} übersprungen`);
      if (report.unmapped_rows.length > 0) {
        parts.push(`${report.unmapped_rows.length} nicht zugeordnet`);
      }
      if (report.malformed_rows.length > 0) {
        parts.push(`${report.malformed_rows.length} fehlerhaft`);
      }
      const allOk = report.unmapped_rows.length === 0 && report.malformed_rows.length === 0;
      setFeedback({ kind: allOk ? "ok" : "error", text: `Import: ${parts.join(", ")}.` });
    } catch (err) {
      setFeedback({ kind: "error", text: extractApiError(err, "Job-Historie-Import fehlgeschlagen.") });
    } finally {
      setImportingJobHistory(false);
    }
  }

  return {
    settings,
    setSettings,
    thresholds,
    setThresholds,
    apiKey,
    setApiKey,
    editKey,
    setEditKey,
    saving,
    testing,
    testResult,
    setTestResult,
    exportingSeed,
    exportingCsv,
    exportingJobHistory,
    importingJobHistory,
    feedback,
    loadError,
    isDirty,
    save,
    discardChanges,
    testConnection,
    downloadSeed,
    downloadCsv,
    downloadJobHistory,
    uploadJobHistory,
  };
}
