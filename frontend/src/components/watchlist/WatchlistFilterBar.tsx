import { ChevronDownIcon, SearchIcon, XIcon } from "../icons";
import { Dropdown, DropdownItem, DropdownSeparator } from "../Dropdown";
import { FilterValues } from "../../hooks/useWatchlistFilters";
import type { ActiveFilter } from "./ActiveFilterChips";

interface Props {
  values: FilterValues;
  onPatch: (patch: Partial<FilterValues>) => void;
  filtersOpen: boolean;
  onToggleFilters: () => void;
  activeFilters: ActiveFilter[];
  presetNames: string[];
  hasActiveFilters: boolean;
  onSavePreset: () => void;
  onApplyPreset: (name: string) => void;
  onDeletePreset: (name: string) => void;
}

export function WatchlistFilterBar({
  values,
  onPatch,
  filtersOpen,
  onToggleFilters,
  activeFilters,
  presetNames,
  hasActiveFilters,
  onSavePreset,
  onApplyPreset,
  onDeletePreset,
}: Props) {
  return (
    <div className="search-bar">
      <div className="search-field">
        <SearchIcon className="search-field-icon" />
        <input
          value={values.query}
          onChange={(e) => onPatch({ query: e.target.value })}
          placeholder="Name oder ISIN suchen…"
          aria-label="Suche"
        />
        {values.query && (
          <button
            type="button"
            className="search-field-clear"
            aria-label="Suche löschen"
            onClick={() => onPatch({ query: "" })}
          >
            <XIcon />
          </button>
        )}
      </div>

      <button
        type="button"
        className={`btn-secondary with-caret ${filtersOpen ? "is-open" : ""}`.trim()}
        onClick={onToggleFilters}
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
            {presetNames.length === 0 && (
              <div className="dropdown-empty">Noch keine Voreinstellungen</div>
            )}
            {presetNames.map((name) => (
              <div className="dropdown-row" key={name}>
                <button
                  type="button"
                  role="menuitem"
                  className="dropdown-item dropdown-item-grow"
                  onClick={() => {
                    close();
                    onApplyPreset(name);
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
                    void onDeletePreset(name);
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
                void onSavePreset();
              }}
              disabled={!hasActiveFilters}
            >
              Aktuelle Filter speichern…
            </DropdownItem>
          </>
        )}
      </Dropdown>
    </div>
  );
}
