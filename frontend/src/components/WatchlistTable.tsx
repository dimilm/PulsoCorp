import { Stock } from "../types";
import {
  changeClass,
  ColorThresholds,
  defaultThresholds,
  dividendClass,
  rowClass,
  scoreClass,
  targetClass,
  valuationClass,
} from "../lib/colorRules";
import { tagColorClass } from "../lib/tagColor";
import RowActionsMenu from "./RowActionsMenu";

const MAX_VISIBLE_TAGS = 3;

interface Props {
  stocks: Stock[];
  sortBy: string;
  sortDir: "asc" | "desc";
  thresholds?: ColorThresholds;
  onSort: (key: string) => void;
  onRefresh: (isin: string) => Promise<void>;
  onEvaluate: (isin: string) => Promise<void>;
  onAiPreview: (isin: string) => Promise<void>;
  onToggleLock: (isin: string, field: string, locked: boolean) => Promise<void>;
  onEdit: (stock: Stock) => void;
  onDelete: (stock: Stock) => Promise<void>;
}

function SortHeader({
  label,
  keyName,
  sortBy,
  sortDir,
  onSort,
}: {
  label: string;
  keyName: string;
  sortBy: string;
  sortDir: "asc" | "desc";
  onSort: (key: string) => void;
}) {
  const marker = sortBy === keyName ? (sortDir === "asc" ? " ▲" : " ▼") : "";
  return (
    <th>
      <button type="button" onClick={() => onSort(keyName)}>
        {label}
        {marker}
      </button>
    </th>
  );
}

export default function WatchlistTable({
  stocks,
  sortBy,
  sortDir,
  thresholds = defaultThresholds,
  onSort,
  onRefresh,
  onEvaluate,
  onAiPreview,
  onToggleLock,
  onEdit,
  onDelete,
}: Props) {
  return (
    <table>
      <thead>
        <tr>
          <SortHeader label="ISIN" keyName="isin" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
          <SortHeader label="Name" keyName="name" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
          <SortHeader label="Sektor" keyName="sector" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
          <th>Tags</th>
          <SortHeader label="Burggraben" keyName="burggraben" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
          <SortHeader label="Tranchen" keyName="tranches" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
          <SortHeader label="Kurs" keyName="current_price" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
          <SortHeader label="Tagesaend. %" keyName="day_change_pct" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
          <SortHeader label="DCF %" keyName="dcf_discount_pct" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
          <SortHeader label="NAV %" keyName="nav_discount_pct" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
          <SortHeader label="Kursziel %" keyName="analyst_target_distance_pct" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
          <SortHeader label="Div. %" keyName="dividend_yield_current" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
          <SortHeader label="Score" keyName="fundamental_score" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
          <SortHeader label="Empfehlung" keyName="recommendation" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
          <SortHeader label="Status" keyName="last_status" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
          <th className="actions-header" aria-label="Aktionen" />
        </tr>
      </thead>
      <tbody>
        {stocks.map((s) => (
          <tr key={s.isin} className={rowClass(s)}>
            <td>{s.isin}</td>
            <td>{s.name}</td>
            <td>{s.sector ?? "-"}</td>
            <td>
              {s.tags && s.tags.length > 0 ? (
                <span className="tag-list">
                  {s.tags.slice(0, MAX_VISIBLE_TAGS).map((t) => (
                    <span key={t} className={`tag-pill tag-pill-sm ${tagColorClass(t)}`}>
                      {t}
                    </span>
                  ))}
                  {s.tags.length > MAX_VISIBLE_TAGS && (
                    <span
                      className="tag-pill tag-pill-sm tag-pill-overflow"
                      title={s.tags.slice(MAX_VISIBLE_TAGS).join(", ")}
                    >
                      +{s.tags.length - MAX_VISIBLE_TAGS}
                    </span>
                  )}
                </span>
              ) : (
                "-"
              )}
            </td>
            <td>{s.burggraben ? "Ja" : "Nein"}</td>
            <td>{s.tranches}</td>
            <td>{s.current_price?.toFixed(2) ?? "-"}</td>
            <td>
              <span className={changeClass(s.day_change_pct, thresholds)}>{s.day_change_pct?.toFixed(2) ?? "-"} </span>
            </td>
            <td>
              <span className={valuationClass(s.dcf_discount_pct)}>{s.dcf_discount_pct?.toFixed(2) ?? "-"}</span>
            </td>
            <td>
              <span className={valuationClass(s.nav_discount_pct)}>{s.nav_discount_pct?.toFixed(2) ?? "-"}</span>
            </td>
            <td>
              <span className={targetClass(s.analyst_target_distance_pct, thresholds)}>
                {s.analyst_target_distance_pct?.toFixed(2) ?? "-"}
              </span>
            </td>
            <td>
              <span className={dividendClass(s.dividend_yield_current, thresholds)}>
                {s.dividend_yield_current?.toFixed(2) ?? "-"}
              </span>
            </td>
            <td>
              <span className={scoreClass(s.fundamental_score, thresholds)}>{s.fundamental_score ?? "-"}</span>
            </td>
            <td>
              {s.recommendation}
              {s.field_sources?.recommendation === "ki_fallback" && (
                <span
                  className="badge badge-fallback"
                  title="Heuristischer Vorschlag - kein echter LLM-Aufruf. Bitte Kontextpruefen."
                >
                  heuristisch
                </span>
              )}
            </td>
            <td>{s.last_status ?? "-"}</td>
            <td className="actions-cell">
              <RowActionsMenu
                stock={s}
                onRefresh={onRefresh}
                onEvaluate={onEvaluate}
                onAiPreview={onAiPreview}
                onToggleLock={onToggleLock}
                onEdit={onEdit}
                onDelete={onDelete}
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
