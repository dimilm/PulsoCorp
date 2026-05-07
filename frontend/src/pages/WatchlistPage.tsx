import { useEffect, useMemo, useRef, useState } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { Modal } from "../components/Modal";
import { PlusIcon, SearchIcon } from "../components/icons";
import { Spinner } from "../components/Spinner";
import WatchlistTable from "../components/WatchlistTable";
import { WatchlistMobileList } from "../components/watchlist/WatchlistMobileList";
import { ActiveFilterChips } from "../components/watchlist/ActiveFilterChips";
import type { ActiveFilter } from "../components/watchlist/ActiveFilterChips";
import { CreateStockModal } from "../components/watchlist/CreateStockModal";
import { WatchlistFilterBar } from "../components/watchlist/WatchlistFilterBar";
import { WatchlistFilterPanel } from "../components/watchlist/WatchlistFilterPanel";
import { WatchlistHeader } from "../components/watchlist/WatchlistHeader";
import { useColorThresholds } from "../hooks/useColorThresholds";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useIsMobile } from "../hooks/useBreakpoint";
import { useJobsAggregate } from "../hooks/useJobsAggregate";
import { usePresets } from "../hooks/usePresets";
import {
  useDeleteStock,
  useRefreshStock,
  useTriggerRefreshAll,
  STOCKS_LIST_KEY,
} from "../hooks/useStockMutations";
import {
  buildStocksParams,
  useWatchlistFilters,
} from "../hooks/useWatchlistFilters";
import { extractApiError } from "../lib/apiError";
import { toast } from "../lib/toast";
import { useCurrentRun, useInvalidateOnRunFinish } from "../lib/runProgress";
import {
  buildWatchlistUrl,
  parseWatchlistUrl,
  searchParamsEqual,
  type SortDir,
} from "../lib/watchlistUrlState";
import { Stock, Tag } from "../types";

// Stable reference so React's effect-dep check does not re-run on every render.
const RUN_INVALIDATE_KEYS = [STOCKS_LIST_KEY, ["dashboard"]] as const;

export function WatchlistPage() {
  useDocumentTitle("Watchlist");
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const [searchParams, setSearchParams] = useSearchParams();

  // Seed filter + sort state from the URL exactly once.
  const initialFromUrl = useMemo(
    () => parseWatchlistUrl(searchParams),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );
  const filters = useWatchlistFilters(initialFromUrl.filters);

  const [sortBy, setSortBy] = useState(initialFromUrl.sortBy);
  const [sortDir, setSortDir] = useState<SortDir>(initialFromUrl.sortDir);

  useEffect(() => {
    const next = buildWatchlistUrl({ filters: filters.debounced, sortBy, sortDir });
    if (searchParamsEqual(next, searchParams)) return;
    setSearchParams(next, { replace: true });
  }, [filters.debounced, sortBy, sortDir, searchParams, setSearchParams]);

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const csvInputRef = useRef<HTMLInputElement | null>(null);

  const thresholds = useColorThresholds();
  const { jobsByIsin, trendsByIsin } = useJobsAggregate();
  const presets = usePresets({
    filterValues: filters.values,
    onApply: filters.applyValues,
  });

  const refreshMutation = useRefreshStock();
  const deleteMutation = useDeleteStock();
  const triggerAllMutation = useTriggerRefreshAll();

  useInvalidateOnRunFinish(RUN_INVALIDATE_KEYS);
  const { data: currentRun } = useCurrentRun();
  const isRunActive = currentRun != null && currentRun.phase !== "finished";

  const stocksQuery = useQuery<Stock[]>({
    queryKey: [...STOCKS_LIST_KEY, filters.debounced],
    queryFn: async () => {
      const res = await api.get("/stocks", { params: buildStocksParams(filters.debounced) });
      return res.data as Stock[];
    },
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    placeholderData: keepPreviousData,
  });
  const stocks = useMemo(() => stocksQuery.data ?? [], [stocksQuery.data]);
  const listLoading = stocksQuery.isFetching;
  const initialLoaded = stocksQuery.data !== undefined;

  const tagsQuery = useQuery<Tag[]>({
    queryKey: ["tags"],
    queryFn: async () => (await api.get("/tags")).data as Tag[],
    staleTime: 60_000,
  });
  const allTags = useMemo(() => tagsQuery.data ?? [], [tagsQuery.data]);
  const tagSuggestions = useMemo(
    () => allTags.map((t) => ({ name: t.name, count: t.count })),
    [allTags]
  );

  const invalidateStocks = async () => {
    await queryClient.invalidateQueries({ queryKey: STOCKS_LIST_KEY });
    await queryClient.invalidateQueries({ queryKey: ["tags"] });
  };

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
      const form = new FormData();
      form.append("file", file);
      await api.post("/import/csv", form);
      await invalidateStocks();
      toast.success("CSV importiert.");
    } catch (err) {
      toast.error(extractApiError(err, "Import fehlgeschlagen."));
    }
  }

  async function deleteStock(stock: Stock) {
    const { confirm } = await import("../lib/dialogs");
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

  const v = filters.values;
  const activeFilters = useMemo<ActiveFilter[]>(() => {
    const list: ActiveFilter[] = [];
    if (v.query.trim())
      list.push({ key: "query", label: `Suche: ${v.query.trim()}`, clear: () => filters.patch({ query: "" }) });
    if (v.sector.trim())
      list.push({ key: "sector", label: `Sektor: ${v.sector.trim()}`, clear: () => filters.patch({ sector: "" }) });
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

      <WatchlistHeader
        stockCount={stocks.length}
        isRunActive={isRunActive}
        onTriggerAll={() => void triggerAll()}
        onImportCsv={() => csvInputRef.current?.click()}
        onExportCsv={() => void exportCsv()}
        onOpenCreate={() => setShowCreateForm(true)}
      />

      <WatchlistFilterBar
        values={v}
        onPatch={filters.patch}
        filtersOpen={filtersOpen}
        onToggleFilters={() => setFiltersOpen((prev) => !prev)}
        activeFilters={activeFilters}
        presetNames={presets.presetNames}
        hasActiveFilters={activeFilters.length > 0}
        onSavePreset={() => void presets.savePresetPrompt()}
        onApplyPreset={presets.applyPreset}
        onDeletePreset={(name) => void presets.deletePreset(name)}
      />

      <ActiveFilterChips activeFilters={activeFilters} onReset={filters.reset} />

      {filtersOpen && !isMobile && (
        <WatchlistFilterPanel
          values={v}
          allTags={allTags}
          onPatch={filters.patch}
          onToggleTag={filters.toggleTag}
          onReset={filters.reset}
        />
      )}

      <Modal
        open={filtersOpen && isMobile}
        onClose={() => setFiltersOpen(false)}
        title="Filter"
        variant="bottomSheet"
        footer={
          <button type="button" className="btn-secondary" onClick={() => { filters.reset(); setFiltersOpen(false); }}>
            Filter zurücksetzen
          </button>
        }
      >
        <WatchlistFilterPanel
          values={v}
          allTags={allTags}
          onPatch={filters.patch}
          onToggleTag={filters.toggleTag}
          onReset={filters.reset}
        />
      </Modal>

      <CreateStockModal
        open={showCreateForm}
        onClose={() => setShowCreateForm(false)}
        tagSuggestions={tagSuggestions}
        onCreated={invalidateStocks}
      />

      {!initialLoaded || (listLoading && stocks.length === 0) ? (
        <Spinner label="Lade Watchlist..." />
      ) : filtered.length === 0 ? (
        activeFilters.length > 0 ? (
          <EmptyState
            icon={<SearchIcon size={20} />}
            title="Keine Treffer für die aktuellen Filter"
            description="Prüfe Suche, Sektor oder Tags – oder setze alle Filter zurück."
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
      ) : isMobile ? (
        <WatchlistMobileList
          stocks={filtered}
          sortBy={sortBy}
          sortDir={sortDir}
          thresholds={thresholds}
          onSort={onSort}
          onRefresh={refresh}
          onEdit={(stock) => navigate(`/stocks/${stock.isin}/edit`)}
          onDelete={deleteStock}
          refreshDisabled={isRunActive}
          jobsByIsin={jobsByIsin}
          trendsByIsin={trendsByIsin}
        />
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
            jobsByIsin={jobsByIsin}
            trendsByIsin={trendsByIsin}
          />
        </div>
      )}
    </div>
  );
}
