import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { api } from "../api/client";
import { Dropdown, DropdownItem, DropdownSeparator } from "../components/Dropdown";
import { ChevronDownIcon, PlusIcon, SearchIcon, XIcon } from "../components/icons";
import { Modal } from "../components/Modal";
import { Spinner } from "../components/Spinner";
import { StockForm, StockFormErrors, StockFormValues } from "../components/StockForm";
import WatchlistTable from "../components/WatchlistTable";
import {
  useDeleteStock,
  useEvaluateStock,
  usePreviewEvaluate,
  useRefreshStock,
  useToggleLock,
  useTriggerRefreshAll,
  STOCKS_QUERY_KEY,
} from "../hooks/useStockMutations";
import {
  buildStocksParams,
  emptyFilters,
  FilterValues,
  useWatchlistFilters,
} from "../hooks/useWatchlistFilters";
import { extractApiError } from "../lib/apiError";
import { ColorThresholds, defaultThresholds } from "../lib/colorRules";
import { Stock, Tag } from "../types";

const EMPTY_STOCK: StockFormValues = {
  isin: "",
  name: "",
  sector: "",
  currency: "EUR",
  burggraben: false,
  tranches: "",
  tags: [],
};

interface ActiveFilter {
  key: string;
  label: string;
  clear: () => void;
}

interface AiPreviewState {
  isin: string;
  recommendation?: string;
  fundamental_score?: number | null;
  fair_value_dcf?: number | null;
  fair_value_nav?: number | null;
  recommendation_reason?: string | null;
  risk_notes?: string | null;
}

function validateStock(values: StockFormValues, requireIsin: boolean): StockFormErrors {
  const errs: StockFormErrors = {};
  if (requireIsin) {
    const isin = values.isin.trim().toUpperCase();
    if (isin.length === 0) {
      errs.isin = "ISIN ist ein Pflichtfeld.";
    } else if (isin.length !== 12) {
      errs.isin = "ISIN muss genau 12 Zeichen lang sein.";
    } else if (!/^[A-Z0-9]{12}$/.test(isin)) {
      errs.isin = "Nur Buchstaben und Ziffern erlaubt.";
    }
  }
  if (!values.name.trim()) {
    errs.name = "Name ist ein Pflichtfeld.";
  }
  if (values.tranches !== "") {
    const numeric = Number(values.tranches);
    if (!Number.isFinite(numeric) || !Number.isInteger(numeric) || numeric < 0) {
      errs.tranches = "Bitte eine ganze Zahl ≥ 0 angeben.";
    }
  }
  return errs;
}

export function WatchlistPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const filters = useWatchlistFilters();

  const [sortBy, setSortBy] = useState("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [showEditForm, setShowEditForm] = useState(false);
  const [editingIsin, setEditingIsin] = useState<string | null>(null);
  const [aiPreview, setAiPreview] = useState<AiPreviewState | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createFieldErrors, setCreateFieldErrors] = useState<StockFormErrors>({});
  const [editError, setEditError] = useState<string | null>(null);
  const [editFieldErrors, setEditFieldErrors] = useState<StockFormErrors>({});
  const [thresholds, setThresholds] = useState<ColorThresholds>(defaultThresholds);
  const [savedPresets, setSavedPresets] = useState<Record<string, FilterValues>>({});
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [newStock, setNewStock] = useState<StockFormValues>(EMPTY_STOCK);
  const csvInputRef = useRef<HTMLInputElement | null>(null);
  const [editStock, setEditStock] = useState<StockFormValues>(EMPTY_STOCK);

  const refreshMutation = useRefreshStock();
  const evaluateMutation = useEvaluateStock();
  const previewMutation = usePreviewEvaluate();
  const toggleLockMutation = useToggleLock();
  const deleteMutation = useDeleteStock();
  const triggerAllMutation = useTriggerRefreshAll();

  const stocksQuery = useQuery<Stock[]>({
    queryKey: [...STOCKS_QUERY_KEY, filters.debounced],
    queryFn: async () => {
      const res = await api.get("/stocks", { params: buildStocksParams(filters.debounced) });
      return res.data as Stock[];
    },
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    placeholderData: keepPreviousData,
  });
  const stocks: Stock[] = stocksQuery.data ?? [];
  const listLoading = stocksQuery.isFetching;
  const initialLoaded = stocksQuery.data !== undefined;

  const tagsQuery = useQuery<Tag[]>({
    queryKey: ["tags"],
    queryFn: async () => (await api.get("/tags")).data as Tag[],
    staleTime: 60_000,
  });
  const allTags = tagsQuery.data ?? [];
  const tagSuggestions = useMemo(
    () => allTags.map((t) => ({ name: t.name, count: t.count })),
    [allTags]
  );

  const invalidateStocks = async () => {
    await queryClient.invalidateQueries({ queryKey: STOCKS_QUERY_KEY });
    await queryClient.invalidateQueries({ queryKey: ["tags"] });
  };

  useEffect(() => {
    const rawThresholds = localStorage.getItem("ct-thresholds");
    if (rawThresholds) {
      try {
        setThresholds({ ...defaultThresholds, ...JSON.parse(rawThresholds) });
      } catch {
        setThresholds(defaultThresholds);
      }
    }
    const rawPresets = localStorage.getItem("ct-presets");
    if (rawPresets) {
      try {
        setSavedPresets(JSON.parse(rawPresets));
      } catch {
        setSavedPresets({});
      }
    }
  }, []);

  async function refresh(isin: string) {
    await refreshMutation.mutateAsync(isin);
  }
  async function evaluate(isin: string) {
    await evaluateMutation.mutateAsync(isin);
  }
  async function previewEvaluate(isin: string) {
    const res = await previewMutation.mutateAsync(isin);
    setAiPreview(res as AiPreviewState);
  }
  async function toggleLock(isin: string, field: string, locked: boolean) {
    await toggleLockMutation.mutateAsync({ isin, field, locked });
  }
  async function triggerAll() {
    try {
      await triggerAllMutation.mutateAsync();
    } catch (error) {
      console.error("refresh-all kickoff failed", error);
    }
    navigate("/runs");
  }
  async function exportCsv() {
    const res = await api.get("/export/csv", { responseType: "blob" });
    const url = URL.createObjectURL(new Blob([res.data], { type: "text/csv" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "watchlist.csv";
    link.click();
    URL.revokeObjectURL(url);
  }
  async function uploadCsvFile(file: File) {
    try {
      // We deliberately do NOT set a Content-Type header here: axios needs to
      // compute the correct multipart boundary itself, otherwise the backend
      // cannot parse the body.
      const form = new FormData();
      form.append("file", file);
      await api.post("/import/csv", form);
      await invalidateStocks();
    } catch (err) {
      alert(extractApiError(err, "Import fehlgeschlagen."));
    }
  }

  function closeCreateModal() {
    setShowCreateForm(false);
    setCreateError(null);
    setCreateFieldErrors({});
    setNewStock(EMPTY_STOCK);
  }

  function closeEditModal() {
    setShowEditForm(false);
    setEditingIsin(null);
    setEditError(null);
    setEditFieldErrors({});
  }

  async function createStock(e: FormEvent) {
    e.preventDefault();
    setCreateError(null);
    const errs = validateStock(newStock, true);
    setCreateFieldErrors(errs);
    if (Object.keys(errs).length > 0) return;
    try {
      await api.post("/stocks", {
        isin: newStock.isin.trim().toUpperCase(),
        name: newStock.name.trim(),
        sector: newStock.sector.trim() || null,
        currency: newStock.currency.trim().toUpperCase() || null,
        burggraben: newStock.burggraben,
        tranches: Math.max(0, Number(newStock.tranches) || 0),
        tags: newStock.tags,
      });
      closeCreateModal();
      await invalidateStocks();
    } catch (error) {
      setCreateError(extractApiError(error, "Unternehmen konnte nicht angelegt werden."));
    }
  }

  function startEdit(stock: Stock) {
    setEditingIsin(stock.isin);
    setEditStock({
      isin: stock.isin,
      name: stock.name ?? "",
      sector: stock.sector ?? "",
      currency: stock.currency ?? "EUR",
      burggraben: stock.burggraben,
      tranches: stock.tranches != null ? String(stock.tranches) : "",
      tags: Array.isArray(stock.tags) ? [...stock.tags] : [],
    });
    setEditError(null);
    setEditFieldErrors({});
    setShowEditForm(true);
  }

  async function saveEdit(e: FormEvent) {
    e.preventDefault();
    if (!editingIsin) return;
    setEditError(null);
    const errs = validateStock(editStock, false);
    setEditFieldErrors(errs);
    if (Object.keys(errs).length > 0) return;
    try {
      await api.patch(`/stocks/${editingIsin}`, {
        name: editStock.name.trim(),
        sector: editStock.sector.trim() || null,
        currency: editStock.currency.trim().toUpperCase() || null,
        burggraben: editStock.burggraben,
        tranches: Math.max(0, Number(editStock.tranches) || 0),
        tags: editStock.tags,
      });
      closeEditModal();
      await invalidateStocks();
    } catch (error) {
      setEditError(extractApiError(error, "Unternehmen konnte nicht aktualisiert werden."));
    }
  }

  async function deleteStock(stock: Stock) {
    const confirmed = window.confirm(`Unternehmen ${stock.name} (${stock.isin}) wirklich loeschen?`);
    if (!confirmed) return;
    try {
      await deleteMutation.mutateAsync(stock.isin);
      if (editingIsin === stock.isin) {
        closeEditModal();
      }
    } catch (error) {
      alert(extractApiError(error, "Loeschen fehlgeschlagen."));
    }
  }

  function onSort(key: string) {
    if (sortBy === key) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
      return;
    }
    setSortBy(key);
    setSortDir("asc");
  }

  function persistPresets(next: Record<string, FilterValues>) {
    setSavedPresets(next);
    localStorage.setItem("ct-presets", JSON.stringify(next));
  }

  function savePresetPrompt() {
    const name = window.prompt("Name für die neue Voreinstellung:");
    if (!name) return;
    const trimmed = name.trim();
    if (!trimmed) return;
    if (savedPresets[trimmed]) {
      const overwrite = window.confirm(`Voreinstellung "${trimmed}" überschreiben?`);
      if (!overwrite) return;
    }
    persistPresets({
      ...savedPresets,
      [trimmed]: filters.values,
    });
  }

  function applyPreset(name: string) {
    const p = savedPresets[name];
    if (!p) return;
    filters.applyValues({ ...emptyFilters, ...p });
  }

  function deletePreset(name: string) {
    const confirmed = window.confirm(`Voreinstellung "${name}" wirklich löschen?`);
    if (!confirmed) return;
    const next = { ...savedPresets };
    delete next[name];
    persistPresets(next);
  }

  const v = filters.values;
  const activeFilters = useMemo<ActiveFilter[]>(() => {
    const list: ActiveFilter[] = [];
    if (v.query.trim())
      list.push({ key: "query", label: `Suche: ${v.query.trim()}`, clear: () => filters.patch({ query: "" }) });
    if (v.sector.trim())
      list.push({ key: "sector", label: `Sektor: ${v.sector.trim()}`, clear: () => filters.patch({ sector: "" }) });
    if (v.onlyBuy)
      list.push({ key: "onlyBuy", label: "Nur BUY", clear: () => filters.patch({ onlyBuy: false }) });
    if (v.onlyMoat)
      list.push({ key: "onlyMoat", label: "Burggraben", clear: () => filters.patch({ onlyMoat: false }) });
    if (v.undervaluedDcf)
      list.push({
        key: "dcf",
        label: "DCF unterbewertet",
        clear: () => filters.patch({ undervaluedDcf: false }),
      });
    if (v.undervaluedNav)
      list.push({
        key: "nav",
        label: "NAV unterbewertet",
        clear: () => filters.patch({ undervaluedNav: false }),
      });
    if (v.scoreMin !== "" || v.scoreMax !== "") {
      const lo = v.scoreMin === "" ? "*" : v.scoreMin;
      const hi = v.scoreMax === "" ? "*" : v.scoreMax;
      list.push({
        key: "score",
        label: `Score ${lo}–${hi}`,
        clear: () => filters.patch({ scoreMin: "", scoreMax: "" }),
      });
    }
    for (const t of v.tags) {
      list.push({ key: `tag:${t}`, label: `Tag: ${t}`, clear: () => filters.toggleTag(t) });
    }
    return list;
  }, [v, filters]);

  const filtered = useMemo(() => {
    const sorted = [...stocks];
    sorted.sort((a, b) => {
      const av = (a as unknown as Record<string, unknown>)[sortBy];
      const bv = (b as unknown as Record<string, unknown>)[sortBy];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === "number" && typeof bv === "number") return sortDir === "asc" ? av - bv : bv - av;
      const cmp = String(av).localeCompare(String(bv), "de");
      return sortDir === "asc" ? cmp : -cmp;
    });
    return sorted;
  }, [stocks, sortBy, sortDir]);

  const presetNames = Object.keys(savedPresets);
  const isCreateValid =
    newStock.isin.trim().length === 12 &&
    /^[A-Z0-9]{12}$/.test(newStock.isin.trim().toUpperCase()) &&
    newStock.name.trim().length > 0;
  const isEditValid = editStock.name.trim().length > 0;
  const createLoading = false; // handled by axios; per-form loading state could be added later
  const editLoading = false;

  return (
    <div className="page">
      <input
        ref={csvInputRef}
        type="file"
        accept=".csv,text/csv"
        style={{ display: "none" }}
        onChange={(ev) => {
          const file = ev.target.files?.[0];
          if (file) void uploadCsvFile(file);
          ev.target.value = "";
        }}
      />
      <header className="page-header">
        <div className="page-header-title">
          <h2>
            Watchlist
            <span className="muted-count"> ({stocks.length})</span>
          </h2>
        </div>
        <div className="page-header-actions">
          <Dropdown
            align="right"
            trigger={({ toggle, open }) => (
              <button
                type="button"
                className={`btn-secondary with-caret ${open ? "is-open" : ""}`.trim()}
                onClick={toggle}
                aria-haspopup="menu"
                aria-expanded={open}
              >
                Daten
                <ChevronDownIcon />
              </button>
            )}
          >
            {(close) => (
              <>
                <DropdownItem
                  onSelect={() => {
                    close();
                    void triggerAll();
                  }}
                >
                  Alle aktualisieren
                </DropdownItem>
                <DropdownItem
                  onSelect={() => {
                    close();
                    csvInputRef.current?.click();
                  }}
                >
                  CSV importieren
                </DropdownItem>
                <DropdownItem
                  onSelect={() => {
                    close();
                    void exportCsv();
                  }}
                >
                  CSV exportieren
                </DropdownItem>
              </>
            )}
          </Dropdown>
          <button type="button" className="btn-primary with-icon" onClick={() => setShowCreateForm(true)}>
            <PlusIcon />
            Unternehmen
          </button>
        </div>
      </header>

      <div className="search-bar">
        <div className="search-field">
          <SearchIcon className="search-field-icon" />
          <input
            value={v.query}
            onChange={(e) => filters.patch({ query: e.target.value })}
            placeholder="Name oder ISIN suchen…"
            aria-label="Suche"
          />
          {v.query && (
            <button
              type="button"
              className="search-field-clear"
              aria-label="Suche löschen"
              onClick={() => filters.patch({ query: "" })}
            >
              <XIcon />
            </button>
          )}
        </div>
        <button
          type="button"
          className={`btn-secondary with-caret ${filtersOpen ? "is-open" : ""}`.trim()}
          onClick={() => setFiltersOpen((prev) => !prev)}
          aria-expanded={filtersOpen}
        >
          Filter
          {activeFilters.length > 0 && <span className="badge">{activeFilters.length}</span>}
          <ChevronDownIcon />
        </button>
        <Dropdown
          align="right"
          trigger={({ toggle, open }) => (
            <button
              type="button"
              className={`btn-secondary with-caret ${open ? "is-open" : ""}`.trim()}
              onClick={toggle}
              aria-haspopup="menu"
              aria-expanded={open}
            >
              Voreinstellungen
              <ChevronDownIcon />
            </button>
          )}
        >
          {(close) => (
            <>
              {presetNames.length === 0 && <div className="dropdown-empty">Noch keine Voreinstellungen</div>}
              {presetNames.map((name) => (
                <div className="dropdown-row" key={name}>
                  <button
                    type="button"
                    role="menuitem"
                    className="dropdown-item dropdown-item-grow"
                    onClick={() => {
                      close();
                      applyPreset(name);
                    }}
                  >
                    {name}
                  </button>
                  <button
                    type="button"
                    className="dropdown-row-action"
                    aria-label={`Voreinstellung ${name} löschen`}
                    onClick={(e) => {
                      e.stopPropagation();
                      deletePreset(name);
                    }}
                  >
                    <XIcon />
                  </button>
                </div>
              ))}
              {presetNames.length > 0 && <DropdownSeparator />}
              <DropdownItem
                onSelect={() => {
                  close();
                  savePresetPrompt();
                }}
                disabled={activeFilters.length === 0}
              >
                Aktuelle Filter speichern…
              </DropdownItem>
            </>
          )}
        </Dropdown>
      </div>

      {activeFilters.length > 0 && (
        <div className="filter-chips" role="list" aria-label="Aktive Filter">
          {activeFilters.map((f) => (
            <span key={f.key} className="filter-chip" role="listitem">
              {f.label}
              <button type="button" aria-label={`${f.label} entfernen`} onClick={f.clear}>
                <XIcon size={12} />
              </button>
            </span>
          ))}
          <button type="button" className="filter-chips-clear" onClick={filters.reset}>
            Alle löschen
          </button>
        </div>
      )}

      {filtersOpen && (
        <section className="filter-panel" aria-label="Erweiterte Filter">
          <div className="filter-grid">
            <div className="filter-group">
              <h4>Klassifizierung</h4>
              <input
                value={v.sector}
                onChange={(e) => filters.patch({ sector: e.target.value })}
                placeholder="Sektor"
              />
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={v.onlyMoat}
                  onChange={(e) => filters.patch({ onlyMoat: e.target.checked })}
                />
                Nur Burggraben
              </label>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={v.onlyBuy}
                  onChange={(e) => filters.patch({ onlyBuy: e.target.checked })}
                />
                Nur BUY
              </label>
            </div>
            <div className="filter-group">
              <h4>Bewertung</h4>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={v.undervaluedDcf}
                  onChange={(e) => filters.patch({ undervaluedDcf: e.target.checked })}
                />
                DCF unterbewertet
              </label>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={v.undervaluedNav}
                  onChange={(e) => filters.patch({ undervaluedNav: e.target.checked })}
                />
                NAV unterbewertet
              </label>
            </div>
            <div className="filter-group">
              <h4>Score</h4>
              <div className="filter-range">
                <input
                  type="number"
                  placeholder="von"
                  value={v.scoreMin}
                  onChange={(e) =>
                    filters.patch({ scoreMin: e.target.value === "" ? "" : Number(e.target.value) })
                  }
                />
                <span className="range-sep">–</span>
                <input
                  type="number"
                  placeholder="bis"
                  value={v.scoreMax}
                  onChange={(e) =>
                    filters.patch({ scoreMax: e.target.value === "" ? "" : Number(e.target.value) })
                  }
                />
              </div>
            </div>
            <div className="filter-group">
              <h4>Tags</h4>
              {allTags.length === 0 ? (
                <span className="filter-tag-empty">Noch keine Tags vergeben.</span>
              ) : (
                <div className="filter-tag-list">
                  {allTags.map((t) => (
                    <label key={t.id} className="checkbox-row">
                      <input
                        type="checkbox"
                        checked={v.tags.includes(t.name)}
                        onChange={() => filters.toggleTag(t.name)}
                      />
                      {t.name}
                      {t.count > 0 && <span className="tag-suggestion-count"> · {t.count}</span>}
                    </label>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div className="filter-panel-footer">
            <button type="button" className="btn-link" onClick={filters.reset}>
              Filter zurücksetzen
            </button>
          </div>
        </section>
      )}

      <Modal
        open={showCreateForm}
        onClose={closeCreateModal}
        title="Unternehmen hinzufügen"
        subtitle="Trage die Stammdaten manuell ein. Marktdaten werden anschließend automatisch ergänzt."
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={closeCreateModal} disabled={createLoading}>
              Abbrechen
            </button>
            <button
              type="submit"
              form="create-stock-form"
              className="btn-primary"
              disabled={createLoading || !isCreateValid}
            >
              {createLoading ? "Speichere…" : "Speichern"}
            </button>
          </>
        }
      >
        <StockForm
          mode="create"
          formId="create-stock-form"
          values={newStock}
          onChange={setNewStock}
          onSubmit={createStock}
          errors={createFieldErrors}
          tagSuggestions={tagSuggestions}
        />
        {createError && (
          <p className="form-banner-error" role="alert">
            {createError}
          </p>
        )}
      </Modal>

      <Modal
        open={showEditForm && !!editingIsin}
        onClose={closeEditModal}
        title="Unternehmen bearbeiten"
        subtitle={
          editingIsin ? (
            <span className="isin-pill" title="ISIN">
              {editingIsin}
            </span>
          ) : null
        }
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={closeEditModal} disabled={editLoading}>
              Abbrechen
            </button>
            <button
              type="submit"
              form="edit-stock-form"
              className="btn-primary"
              disabled={editLoading || !isEditValid}
            >
              {editLoading ? "Speichere…" : "Änderungen speichern"}
            </button>
          </>
        }
      >
        <StockForm
          mode="edit"
          formId="edit-stock-form"
          values={editStock}
          onChange={setEditStock}
          onSubmit={saveEdit}
          errors={editFieldErrors}
          tagSuggestions={tagSuggestions}
        />
        {editError && (
          <p className="form-banner-error" role="alert">
            {editError}
          </p>
        )}
      </Modal>
      {!initialLoaded || (listLoading && stocks.length === 0) ? (
        <Spinner label="Lade Watchlist..." />
      ) : (
        <div className={listLoading ? "table-wrapper is-loading" : "table-wrapper"}>
          {listLoading && (
            <div className="table-overlay">
              <div className="table-overlay-indicator" role="status" aria-live="polite">
                <div className="spinner" aria-hidden="true" />
                <span>Aktualisiere…</span>
              </div>
            </div>
          )}
          <WatchlistTable
            stocks={filtered}
            sortBy={sortBy}
            sortDir={sortDir}
            thresholds={thresholds}
            onSort={onSort}
            onRefresh={refresh}
            onEvaluate={evaluate}
            onAiPreview={previewEvaluate}
            onToggleLock={toggleLock}
            onEdit={startEdit}
            onDelete={deleteStock}
          />
        </div>
      )}
      {aiPreview && (
        <div className="create-stock-form">
          <h3>KI Vorschlag fuer {aiPreview.isin}</h3>
          <p>Empfehlung: {aiPreview.recommendation}</p>
          <p>Score: {aiPreview.fundamental_score}</p>
          <p>DCF: {Number(aiPreview.fair_value_dcf ?? 0).toFixed(2)}</p>
          <p>NAV: {Number(aiPreview.fair_value_nav ?? 0).toFixed(2)}</p>
          <p>Grund: {aiPreview.recommendation_reason || "-"}</p>
          <p>Risiken: {aiPreview.risk_notes || "-"}</p>
          <div className="form-actions">
            <button
              type="button"
              className="btn-primary"
              onClick={async () => {
                await evaluate(aiPreview.isin);
                setAiPreview(null);
              }}
            >
              Übernehmen
            </button>
            <button type="button" className="btn-secondary" onClick={() => setAiPreview(null)}>
              Verwerfen
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
