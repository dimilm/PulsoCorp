import { FormEvent, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "../api/client";
import { Spinner } from "../components/Spinner";
import { TagInput } from "../components/TagInput";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { STOCKS_LIST_KEY, useDeleteStock } from "../hooks/useStockMutations";
import { useStock } from "../hooks/useStockQueries";
import { extractApiError } from "../lib/apiError";
import { confirm } from "../lib/dialogs";
import { editStockSchema, type EditStockFormShape } from "../lib/stockFormSchemas";
import { toast } from "../lib/toast";
import { type Errors, validateSchema } from "../lib/validation";
import type { Stock, Tag } from "../types";

const KNOWN_CURRENCIES = ["EUR", "USD", "CHF", "GBP", "JPY"] as const;

interface FormState {
  name: string;
  sector: string;
  currency: string;
  tranches: string;
  ticker_override: string;
  tags: string[];
  reasoning: string;
  link_yahoo: string;
  link_finanzen: string;
  link_onvista_chart: string;
  link_onvista_fundamental: string;
}

function fromStock(stock: Stock): FormState {
  return {
    name: stock.name ?? "",
    sector: stock.sector ?? "",
    currency: stock.currency ?? "EUR",
    tranches: stock.tranches != null ? String(stock.tranches) : "0",
    ticker_override: stock.ticker_override ?? "",
    tags: Array.isArray(stock.tags) ? [...stock.tags] : [],
    reasoning: stock.reasoning ?? "",
    link_yahoo: stock.link_yahoo ?? "",
    link_finanzen: stock.link_finanzen ?? "",
    link_onvista_chart: stock.link_onvista_chart ?? "",
    link_onvista_fundamental: stock.link_onvista_fundamental ?? "",
  };
}

function emptyOrNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

function parseInteger(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  const n = Number(trimmed);
  return Number.isInteger(n) ? n : null;
}

/** Project the wider local FormState onto the subset that the edit-schema
 *  validates. Avoids accidentally validating fields that have no rules
 *  (sector, tags, reasoning). */
function toEditShape(state: FormState): EditStockFormShape {
  return {
    name: state.name,
    currency: state.currency,
    tranches: state.tranches,
    ticker_override: state.ticker_override,
    link_yahoo: state.link_yahoo,
    link_finanzen: state.link_finanzen,
    link_onvista_chart: state.link_onvista_chart,
    link_onvista_fundamental: state.link_onvista_fundamental,
  };
}

export function StockEditPage() {
  const { isin } = useParams<{ isin: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const stockQuery = useStock(isin);
  const deleteMutation = useDeleteStock();
  const stock = stockQuery.data;
  useDocumentTitle(stock ? `${stock.name} bearbeiten` : "Bearbeiten");

  const tagsQuery = useQuery<Tag[]>({
    queryKey: ["tags"],
    queryFn: async () => (await api.get("/tags")).data as Tag[],
    staleTime: 60_000,
  });
  const tagSuggestions = useMemo(
    () => (tagsQuery.data ?? []).map((t) => ({ name: t.name, count: t.count })),
    [tagsQuery.data]
  );

  const [form, setForm] = useState<FormState | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Errors<EditStockFormShape>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  useEffect(() => {
    if (stock && !form) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setForm(fromStock(stock));
    }
  }, [stock, form]);

  if (!isin) {
    return (
      <div className="page">
        <p>Keine ISIN angegeben.</p>
        <Link to="/watchlist" className="btn-secondary">Zurück zur Watchlist</Link>
      </div>
    );
  }

  if (stockQuery.isLoading && !stock) {
    return (
      <div className="page">
        <Spinner label="Lade Bearbeitungsmaske..." />
      </div>
    );
  }

  if (stockQuery.isError || !stock || !form) {
    return (
      <div className="page">
        <p className="form-banner-error">
          {extractApiError(stockQuery.error, "Unternehmen konnte nicht geladen werden.")}
        </p>
        <Link to="/watchlist" className="btn-secondary">Zurück zur Watchlist</Link>
      </div>
    );
  }

  const isCustomCurrency =
    form.currency !== "" && !(KNOWN_CURRENCIES as readonly string[]).includes(form.currency);

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
    // Clear the field's error eagerly so the user sees feedback as soon as
    // they start fixing it instead of waiting for the next submit attempt.
    if (key in fieldErrors) {
      setFieldErrors((prev) => {
        if (!(key in prev)) return prev;
        const next = { ...prev };
        delete next[key as keyof EditStockFormShape];
        return next;
      });
    }
  }

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    if (!form) return;
    const errors = validateSchema(toEditShape(form), editStockSchema);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) {
      setError("Bitte markierte Felder korrigieren.");
      return;
    }
    setError(null);
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        sector: emptyOrNull(form.sector),
        currency: emptyOrNull(form.currency.toUpperCase()),
        tranches: Math.max(0, parseInteger(form.tranches) ?? 0),
        ticker_override: emptyOrNull(form.ticker_override),
        tags: form.tags,
        reasoning: emptyOrNull(form.reasoning),
        link_yahoo: emptyOrNull(form.link_yahoo),
        link_finanzen: emptyOrNull(form.link_finanzen),
        link_onvista_chart: emptyOrNull(form.link_onvista_chart),
        link_onvista_fundamental: emptyOrNull(form.link_onvista_fundamental),
      };
      const res = await api.patch(`/stocks/${isin}`, payload);
      const updated = res.data as Stock;
      queryClient.setQueryData(["stocks", "detail", isin], updated);
      await queryClient.invalidateQueries({ queryKey: STOCKS_LIST_KEY });
      await queryClient.invalidateQueries({ queryKey: ["tags"] });
      setForm(fromStock(updated));
      setSavedAt(new Date().toLocaleTimeString("de-DE"));
      toast.success("Änderungen gespeichert.");
    } catch (e2) {
      const message = extractApiError(e2, "Speichern fehlgeschlagen.");
      setError(message);
      toast.error(message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!stock) return;
    const ok = await confirm({
      title: "Unternehmen löschen",
      message: `Unternehmen ${stock.name} (${stock.isin}) wirklich löschen?`,
      destructive: true,
      confirmLabel: "Löschen",
    });
    if (!ok) return;
    try {
      await deleteMutation.mutateAsync(isin!);
      toast.success(`${stock.name} gelöscht.`);
      navigate("/watchlist");
    } catch (e) {
      toast.error(extractApiError(e, "Löschen fehlgeschlagen."));
    }
  }

  return (
    <div className="page edit-page">
      <header className="detail-breadcrumb">
        <Link to="/watchlist" className="breadcrumb-link">Watchlist</Link>
        <span className="breadcrumb-sep">›</span>
        <Link to={`/stocks/${stock.isin}`} className="breadcrumb-link">{stock.name}</Link>
        <span className="breadcrumb-sep">›</span>
        <span className="breadcrumb-current">Bearbeiten</span>
      </header>

      <div className="edit-page-header">
        <div>
          <h2>{stock.name} bearbeiten</h2>
          <span className="isin-pill" title="ISIN">{stock.isin}</span>
        </div>
        <div className="edit-page-header-actions">
          <Link to={`/stocks/${stock.isin}`} className="btn-secondary">
            Abbrechen
          </Link>
          <button
            type="submit"
            form="edit-stock-page-form"
            className="btn-primary"
            disabled={saving}
          >
            {saving ? "Speichere…" : "Änderungen speichern"}
          </button>
        </div>
      </div>

      {error && (
        <p className="form-banner-error" role="alert">
          {error}
        </p>
      )}
      {savedAt && !error && (
        <p className="form-banner-success" role="status">
          Gespeichert um {savedAt}.
        </p>
      )}

      <form id="edit-stock-page-form" className="edit-form" onSubmit={handleSave} noValidate>
        <div className="edit-grid">
          <section className="edit-card">
            <h3>Stammdaten</h3>
            <div className={`field ${fieldErrors.name ? "has-error" : ""}`}>
              <label htmlFor="edit-name">
                Name <span className="required" aria-hidden="true">*</span>
              </label>
              <input
                id="edit-name"
                value={form.name}
                onChange={(e) => set("name", e.target.value)}
                aria-invalid={fieldErrors.name ? true : undefined}
                aria-describedby={fieldErrors.name ? "edit-name-error" : undefined}
                required
              />
              {fieldErrors.name && (
                <div id="edit-name-error" className="field-error">
                  {fieldErrors.name}
                </div>
              )}
            </div>
            <div className="field">
              <label htmlFor="edit-sector">Sektor</label>
              <input
                id="edit-sector"
                value={form.sector}
                onChange={(e) => set("sector", e.target.value)}
                placeholder="z. B. Industrie, Tech"
              />
            </div>
            <div className="field-row">
              <div className={`field ${fieldErrors.currency ? "has-error" : ""}`}>
                <label htmlFor="edit-currency">Währung</label>
                <select
                  id="edit-currency"
                  value={isCustomCurrency ? "__other__" : form.currency || "EUR"}
                  onChange={(e) => {
                    const v = e.target.value;
                    if (v === "__other__") {
                      set("currency", isCustomCurrency ? form.currency : "");
                    } else {
                      set("currency", v);
                    }
                  }}
                >
                  {KNOWN_CURRENCIES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                  <option value="__other__">Andere…</option>
                </select>
                {isCustomCurrency && (
                  <input
                    className="field-extra"
                    value={form.currency}
                    onChange={(e) => set("currency", e.target.value.toUpperCase().slice(0, 3))}
                    placeholder="ISO-Code"
                    maxLength={3}
                    aria-invalid={fieldErrors.currency ? true : undefined}
                  />
                )}
                {fieldErrors.currency && (
                  <div className="field-error">{fieldErrors.currency}</div>
                )}
              </div>
              <div className={`field ${fieldErrors.tranches ? "has-error" : ""}`}>
                <label htmlFor="edit-tranches">Tranchen</label>
                <input
                  id="edit-tranches"
                  type="number"
                  min={0}
                  inputMode="numeric"
                  value={form.tranches}
                  onChange={(e) => set("tranches", e.target.value)}
                  aria-invalid={fieldErrors.tranches ? true : undefined}
                  aria-describedby={fieldErrors.tranches ? "edit-tranches-error" : undefined}
                />
                <span className="helper">Anzahl gekaufter Positionen</span>
                {fieldErrors.tranches && (
                  <div id="edit-tranches-error" className="field-error">
                    {fieldErrors.tranches}
                  </div>
                )}
              </div>
            </div>
            <div className={`field ${fieldErrors.ticker_override ? "has-error" : ""}`}>
              <label htmlFor="edit-ticker">Ticker (Override)</label>
              <input
                id="edit-ticker"
                value={form.ticker_override}
                onChange={(e) => set("ticker_override", e.target.value.toUpperCase().trim())}
                placeholder="Optional, z. B. SIE.DE"
                aria-invalid={fieldErrors.ticker_override ? true : undefined}
                aria-describedby={fieldErrors.ticker_override ? "edit-ticker-error" : undefined}
              />
              <span className="helper">
                Überschreibt die automatische Symbol-Erkennung beim Provider.
              </span>
              {fieldErrors.ticker_override && (
                <div id="edit-ticker-error" className="field-error">
                  {fieldErrors.ticker_override}
                </div>
              )}
            </div>
            <div className="field">
              <label htmlFor="edit-tags">Tags</label>
              <TagInput
                id="edit-tags"
                value={form.tags}
                onChange={(next) => set("tags", next)}
                suggestions={tagSuggestions}
              />
            </div>
          </section>

          <section className="edit-card">
            <h3>Notizen & Reasoning</h3>
            <div className="field">
              <label htmlFor="edit-reasoning">Persönliche Notizen</label>
              <textarea
                id="edit-reasoning"
                value={form.reasoning}
                onChange={(e) => set("reasoning", e.target.value)}
                rows={6}
                placeholder="Eigene Investmentthese, Beobachtungen, Auslöser…"
              />
            </div>
            <h4 className="edit-subsection">Externe Links</h4>
            <div className={`field ${fieldErrors.link_yahoo ? "has-error" : ""}`}>
              <label htmlFor="edit-link-yahoo">Yahoo Finance</label>
              <input
                id="edit-link-yahoo"
                value={form.link_yahoo}
                onChange={(e) => set("link_yahoo", e.target.value)}
                placeholder="https://finance.yahoo.com/quote/…"
                aria-invalid={fieldErrors.link_yahoo ? true : undefined}
              />
              {fieldErrors.link_yahoo && (
                <div className="field-error">{fieldErrors.link_yahoo}</div>
              )}
            </div>
            <div className={`field ${fieldErrors.link_finanzen ? "has-error" : ""}`}>
              <label htmlFor="edit-link-finanzen">Finanzen.net</label>
              <input
                id="edit-link-finanzen"
                value={form.link_finanzen}
                onChange={(e) => set("link_finanzen", e.target.value)}
                placeholder="https://www.finanzen.net/aktien/…"
                aria-invalid={fieldErrors.link_finanzen ? true : undefined}
              />
              {fieldErrors.link_finanzen && (
                <div className="field-error">{fieldErrors.link_finanzen}</div>
              )}
            </div>
            <div className={`field ${fieldErrors.link_onvista_chart ? "has-error" : ""}`}>
              <label htmlFor="edit-link-chart">Onvista Chart</label>
              <input
                id="edit-link-chart"
                value={form.link_onvista_chart}
                onChange={(e) => set("link_onvista_chart", e.target.value)}
                placeholder="https://www.onvista.de/aktien/chart/…"
                aria-invalid={fieldErrors.link_onvista_chart ? true : undefined}
              />
              {fieldErrors.link_onvista_chart && (
                <div className="field-error">{fieldErrors.link_onvista_chart}</div>
              )}
            </div>
            <div className={`field ${fieldErrors.link_onvista_fundamental ? "has-error" : ""}`}>
              <label htmlFor="edit-link-fundamental">Onvista Fundamentals</label>
              <input
                id="edit-link-fundamental"
                value={form.link_onvista_fundamental}
                onChange={(e) => set("link_onvista_fundamental", e.target.value)}
                placeholder="https://www.onvista.de/aktien/fundamental/…"
                aria-invalid={fieldErrors.link_onvista_fundamental ? true : undefined}
              />
              {fieldErrors.link_onvista_fundamental && (
                <div className="field-error">{fieldErrors.link_onvista_fundamental}</div>
              )}
            </div>
          </section>
        </div>

        <div className="edit-action-bar">
          <Link to={`/stocks/${stock.isin}`} className="btn-secondary">
            Abbrechen
          </Link>
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? "Speichere…" : "Änderungen speichern"}
          </button>
        </div>
      </form>

      <section className="detail-card edit-danger-section">
        <div className="detail-card-head">
          <h3>Gefahrenzone</h3>
        </div>
        <div className="detail-danger-zone">
          <div>
            <strong>Unternehmen löschen</strong>
            <p>
              Entfernt das Unternehmen samt Marktdaten und Historie. Diese Aktion ist
              nicht umkehrbar.
            </p>
          </div>
          <button
            type="button"
            className="btn-danger"
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
          >
            {deleteMutation.isPending ? "Lösche…" : "Löschen"}
          </button>
        </div>
      </section>
    </div>
  );
}

export default StockEditPage;
