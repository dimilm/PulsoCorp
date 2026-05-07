import { useState } from "react";

import { WatchlistMobileCard } from "./WatchlistMobileCard";
import { Dropdown, DropdownItem } from "../Dropdown";
import { SortIcon } from "../icons";
import type { JobsAggregate } from "../WatchlistTable";
import type { ColorThresholds } from "../../lib/colorRules";
import { defaultThresholds } from "../../lib/colorRules";
import type { JobsTrendPoint } from "../../hooks/useJobsTrendsAggregate";
import type { Stock } from "../../types";

type SortDir = "asc" | "desc";

const SORT_OPTIONS: { key: string; label: string }[] = [
  { key: "name", label: "Name" },
  { key: "current_price", label: "Kurs" },
  { key: "day_change_pct", label: "Tagesänderung" },
  { key: "analyst_target_distance_pct", label: "Kursziel-Distanz" },
  { key: "dividend_yield_current", label: "Dividende" },
  { key: "last_status", label: "Status" },
  { key: "sector", label: "Sektor" },
  { key: "tranches", label: "Tranchen" },
];

interface Props {
  stocks: Stock[];
  sortBy: string;
  sortDir: SortDir;
  thresholds?: ColorThresholds;
  onSort: (key: string) => void;
  onRefresh: (isin: string) => Promise<void>;
  onEdit: (stock: Stock) => void;
  onDelete: (stock: Stock) => Promise<void>;
  refreshDisabled?: boolean;
  jobsByIsin?: Record<string, JobsAggregate>;
  trendsByIsin?: Record<string, JobsTrendPoint[]>;
}

export function WatchlistMobileList({
  stocks,
  sortBy,
  sortDir,
  thresholds = defaultThresholds,
  onSort,
  onRefresh,
  onEdit,
  onDelete,
  refreshDisabled = false,
  jobsByIsin,
  trendsByIsin,
}: Props) {
  const [localSortDir, setLocalSortDir] = useState<SortDir>(sortDir);

  const activeSortLabel =
    SORT_OPTIONS.find((o) => o.key === sortBy)?.label ?? "Sortieren";

  function handleSort(key: string) {
    if (key === sortBy) {
      const next: SortDir = localSortDir === "asc" ? "desc" : "asc";
      setLocalSortDir(next);
      onSort(key);
    } else {
      setLocalSortDir("asc");
      onSort(key);
    }
  }

  return (
    <div className="wl-mobile-list">
      {/* Sort control */}
      <div className="wl-mobile-sort-bar">
        <Dropdown
          align="left"
          trigger={({ open, toggle }) => (
            <button
              type="button"
              className={`btn-secondary btn-sm with-icon ${open ? "is-open" : ""}`}
              onClick={toggle}
              aria-label="Sortierung ändern"
            >
              <SortIcon size={14} />
              {activeSortLabel}
            </button>
          )}
        >
          {(close) => (
            <>
              {SORT_OPTIONS.map((opt) => (
                <DropdownItem
                  key={opt.key}
                  onSelect={() => {
                    handleSort(opt.key);
                    close();
                  }}
                >
                  {opt.key === sortBy && (localSortDir === "asc" ? "▲ " : "▼ ")}
                  {opt.label}
                </DropdownItem>
              ))}
            </>
          )}
        </Dropdown>
        <button
          type="button"
          className="btn-secondary btn-sm"
          onClick={() => handleSort(sortBy)}
          aria-label={localSortDir === "asc" ? "Absteigend sortieren" : "Aufsteigend sortieren"}
          title={localSortDir === "asc" ? "Absteigend sortieren" : "Aufsteigend sortieren"}
        >
          {localSortDir === "asc" ? "▲" : "▼"}
        </button>
        <span className="wl-mobile-count">{stocks.length} Einträge</span>
      </div>

      {/* Card list */}
      <div className="wl-mobile-cards">
        {stocks.map((stock) => (
          <WatchlistMobileCard
            key={stock.isin}
            stock={stock}
            thresholds={thresholds}
            onRefresh={onRefresh}
            onEdit={onEdit}
            onDelete={onDelete}
            refreshDisabled={refreshDisabled}
            jobsAggregate={jobsByIsin?.[stock.isin]}
            trendPoints={trendsByIsin?.[stock.isin]}
          />
        ))}
      </div>
    </div>
  );
}
