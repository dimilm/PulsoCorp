import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import { CreateStockForm, StockFormErrors, StockFormValues } from "../components/CreateStockForm";
import { Dropdown, DropdownItem, DropdownSeparator } from "../components/Dropdown";
import { EmptyState } from "../components/EmptyState";
import { ChevronDownIcon, PlusIcon, SearchIcon, XIcon } from "../components/icons";
import { Modal } from "../components/Modal";
import { Spinner } from "../components/Spinner";
import WatchlistTable from "../components/WatchlistTable";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import {
  useDeleteStock,
  useRefreshStock,
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
import { confirm, prompt } from "../lib/dialogs";
import { toast } from "../lib/toast";
import { useCurrentRun, useInvalidateOnRunFinish } from "../lib/runProgress";
import { validateCreateStock } from "../lib/stockValidation";
import {
  buildWatchlistUrl,
  parseWatchlistUrl,
  searchParamsEqual,
  type SortDir,
} from "../lib/watchlistUrlState";
import { Stock, Tag } from "../types";

// Stable reference so React's effect-dep check does not re-run on every render.
const RUN_INVALIDATE_KEYS = [STOCKS_QUERY_KEY, ["dashboard"]] as const;

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

export function WatchlistPage() {
  useDocumentTitle("Watchlist");
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Seed filter + sort state from the URL exactly once. The page then mirrors
  // both back into `?q=…&sortBy=…&sortDir=…` whenever the user changes them
  // (debounced on the filters side), so refreshes, deep-links and the
  // browser's back button all stay in sync without polluting the history.
  const initialFromUrl = useMemo(
    () => parseWatchlistUrl(searchParams),
    // We intentionally read the URL only on mount: subsequent navigations
    // inside the page should not reset the local state again.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );
  const filters = useWatchlistFilters(initialFromUrl.filters);

  const [sortBy, setSortBy] = useState(initialFromUrl.sortBy);
  const [sortDir, setSortDir] = useState<SortDir>(initialFromUrl.sortDir);

  useEffect(() => {
    const next = buildWatchlistUrl({
      filters: filters.debounced,
      sortBy,
      sortDir,
    });
    if (searchParamsEqual(next, searchParams)) return;
    setSearchParams(next, { replace: true });
  }, [filters.debounced, sortBy, sortDir, searchParams, setSearchParams]);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createFieldErrors, setCreateFieldErrors] = useState<StockFormErrors>({});
  const [thresholds, setThresholds] = useState<ColorThresholds>(defaultThresholds);
  const [savedPresets, setSavedPresets] = useState<Record<string, FilterValues>>({});
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [newStock, setNewStock] = useState<StockFormValues>(EMPTY_STOCK);
  const csvInputRef = useRef<HTMLInputElement | null>(null);

  const refreshMutation = useRefreshStock();
  const deleteMutation = useDeleteStock();
  const triggerAllMutation = useTriggerRefreshAll();

  // Single-stock and bulk refreshes both run asynchronously now, so the table
  // would otherwise show stale data until the user refetched manually. Hook
  // into the global run-current feed and invalidate the stock cache the
  // moment any run finishes.
  useInvalidateOnRunFinish(RUN_INVALIDATE_KEYS);

  // Same flag drives the per-row "Aktualisieren" item and the toolbar
  // "Alle aktualisieren" item: the backend rejects parallel jobs with
  // `already_running`, so we disable the entry points instead of letting users
  // click into a 409.
  const { data: currentRun } = useCurrentRun();
  const isRunActive = currentRun != null && currentRun.phase !== "finished";

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
    try {
      await refreshMutation.mutateAsync(isin);
    } catch (error) {
      toast.error(extractApiError(error, "Aktualisierung konnte nicht gestartet werden."));
    }
  }
  async function triggerAll() {
    try {
      await triggerAllMutation.mutateAsync();
    } catch (error) {
      toast.error(extractApiError(error, "Refresh-All konnte nicht gestartet werden."));
      return;
    }
    navigate("/runs");
  }
  async function exportCsv() {
    try {
      const res = await api.get("/export/csv", { responseType: "blob" });
      const url = URL.createObjectURL(new Blob([res.data], { type: "text/csv" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = "watchlist.csv";
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast.error(extractApiError(error, "Export fehlgeschlagen."));
    }
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
      toast.success("CSV importiert.");
    } catch (err) {
      toast.error(extractApiError(err, "Import fehlgeschlagen."));
    }
  }

  function closeCreateModal() {
    setShowCreateForm(false);
    setCreateError(null);
    setCreateFieldErrors({});
    setNewStock(EMPTY_STOCK);
  }

  async function createStock(e: FormEvent) {
    e.preventDefault();
    setCreateError(null);
    const errs = validateCreateStock(newStock);
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

  async function deleteStock(stock: Stock) {
    const confirmed = await confirm({
      title: "Unternehmen löschen",
      message: `Unternehmen ${stock.name} (${stock.isin}) wirklich löschen?`,
      destructive: true,
      confirmLabel: "Löschen",
    });
    if (!confirmed) return;
    try {
      await deleteMutation.mutateAsync(stock.isin);
      toast.success(`${stock.name} gelöscht.`);
    } catch (error) {
      toast.error(extractApiError(error, "Löschen fehlgeschlagen."));
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

  async function savePresetPrompt() {
    const name = await prompt({
      title: "Voreinstellung speichern",
      message: "Wie soll die Voreinstellung heißen?",
      placeholder: "z. B. Dividendenfokus",
      confirmLabel: "Speichern",
      validate: (value) => (value.trim() ? null : "Bitte einen Namen eingeben."),
    });
    if (!name) return;
    const trimmed = name.trim();
    if (!trimmed) return;
    if (savedPresets[trimmed]) {
      const overwrite = await confirm({
        title: "Voreinstellung überschreiben",
        message: `Voreinstellung "${trimmed}" überschreiben?`,
      });
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

  async function deletePreset(name: string) {
    const confirmed = await confirm({
      title: "Voreinstellung löschen",
      message: `Voreinstellung "${name}" wirklich löschen?`,
      destructive: true,
    });
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
    if (v.onlyMoat)
      list.push({ key: "onlyMoat", label: "Burggraben", clear: () => filters.patch({ onlyMoat: false }) });
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
  const createLoading = false; // handled by axios; per-form loading state could be added later

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
                  disabled={isRunActive}
                  onSelect={() => {
                    close();
                    void triggerAll();
                  }}
                >
                  {isRunActive ? "Aktualisierung läuft…" : "Alle aktualisieren"}
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
                      void deletePreset(name);
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
                  void savePresetPrompt();
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
        <CreateStockForm
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

      {!initialLoaded || (listLoading && stocks.length === 0) ? (
        <Spinner label="Lade Watchlist..." />
      ) : filtered.length === 0 ? (
        activeFilters.length > 0 ? (
          <EmptyState
            icon={<SearchIcon size={20} />}
            title="Keine Treffer für die aktuellen Filter"
            description="Prüfe Suche, Sektor, Tags oder den Burggraben-Schalter – oder setze alle Filter zurück."
            action={
              <button type="button" className="btn-secondary" onClick={filters.reset}>
                Filter zurücksetzen
              </button>
            }
          />
        ) : (
          <EmptyState
            icon={<PlusIcon size={20} />}
            title="Noch keine Unternehmen in der Watchlist"
            description="Lege das erste Unternehmen an, importiere eine CSV-Datei oder synchronisiere deine bestehende Liste, um Marktdaten zu sehen."
            action={
              <>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => setShowCreateForm(true)}
                >
                  Erstes Unternehmen anlegen
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => csvInputRef.current?.click()}
                >
                  CSV importieren
                </button>
              </>
            }
          />
        )
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
            onEdit={(stock) => navigate(`/stocks/${stock.isin}/edit`)}
            onDelete={deleteStock}
            refreshDisabled={isRunActive}
          />
        </div>
      )}
    </div>
  );
}
