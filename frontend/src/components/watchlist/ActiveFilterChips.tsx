import { XIcon } from "../icons";

export interface ActiveFilter {
  key: string;
  label: string;
  clear: () => void;
}

interface Props {
  activeFilters: ActiveFilter[];
  onReset: () => void;
}

export function ActiveFilterChips({ activeFilters, onReset }: Props) {
  if (activeFilters.length === 0) return null;

  return (
    <div className="filter-chips" role="list" aria-label="Aktive Filter">
      {activeFilters.map((f) => (
        <span key={f.key} className="filter-chip" role="listitem">
          {f.label}
          <button type="button" aria-label={`${f.label} entfernen`} onClick={f.clear}>
            <XIcon size={12} />
          </button>
        </span>
      ))}
      <button type="button" className="filter-chips-clear" onClick={onReset}>
        Alle löschen
      </button>
    </div>
  );
}
