import { FilterValues } from "../../hooks/useWatchlistFilters";
import { Tag } from "../../types";

interface Props {
  values: FilterValues;
  allTags: Tag[];
  onPatch: (patch: Partial<FilterValues>) => void;
  onToggleTag: (tag: string) => void;
  onReset: () => void;
}

export function WatchlistFilterPanel({ values, allTags, onPatch, onToggleTag, onReset }: Props) {
  return (
    <section className="filter-panel" aria-label="Erweiterte Filter">
      <div className="filter-grid">
        <div className="filter-group">
          <h4>Klassifizierung</h4>
          <input
            value={values.sector}
            onChange={(e) => onPatch({ sector: e.target.value })}
            placeholder="Sektor"
          />
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
                    checked={values.tags.includes(t.name)}
                    onChange={() => onToggleTag(t.name)}
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
        <button type="button" className="btn-link" onClick={onReset}>
          Filter zurücksetzen
        </button>
      </div>
    </section>
  );
}
