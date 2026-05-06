import { KeyboardEvent, useMemo, useState } from "react";
import { SectorSuggestion } from "../hooks/useStockQueries";

export interface SectorAutocompleteProps {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  suggestions?: SectorSuggestion[];
  disabled?: boolean;
  placeholder?: string;
}

/**
 * Returns suggestions whose name contains the query (case-insensitive),
 * limited to a maximum of 8 results.
 */
export function filterSuggestions(
  query: string,
  suggestions: SectorSuggestion[]
): SectorSuggestion[] {
  const q = query.trim().toLowerCase();
  return suggestions
    .filter((s) => !q || s.name.toLowerCase().includes(q))
    .slice(0, 8);
}

/**
 * Returns the next active index when navigating down (with wrap-around).
 */
export function navigateDown(activeIndex: number, length: number): number {
  return (activeIndex + 1) % length;
}

/**
 * Returns the next active index when navigating up (with wrap-around).
 */
export function navigateUp(activeIndex: number, length: number): number {
  return (activeIndex - 1 + length) % length;
}

export function SectorAutocomplete({
  id,
  value,
  onChange,
  suggestions,
  disabled,
  placeholder,
}: SectorAutocompleteProps) {
  const [focused, setFocused] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);

  const filtered = useMemo(
    () => filterSuggestions(value, suggestions ?? []),
    [value, suggestions]
  );

  const showDropdown = focused && filtered.length > 0;

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (!showDropdown) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => navigateDown(i, filtered.length));
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => navigateUp(i, filtered.length));
      return;
    }
    if (e.key === "Enter") {
      const suggestion = filtered[activeIndex];
      if (suggestion) {
        e.preventDefault();
        onChange(suggestion.name);
        setFocused(false);
      }
      return;
    }
    if (e.key === "Escape") {
      setFocused(false);
      return;
    }
  }

  return (
    <div style={{ position: "relative" }}>
      <input
        id={id}
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setActiveIndex(0);
        }}
        onFocus={() => setFocused(true)}
        onBlur={() => setTimeout(() => setFocused(false), 120)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={placeholder}
        autoComplete="off"
      />
      {showDropdown && (
        <div className="tag-suggestions" role="listbox">
          {filtered.map((s, idx) => (
            <button
              key={s.name}
              type="button"
              role="option"
              aria-selected={idx === activeIndex}
              className={`tag-suggestion ${idx === activeIndex ? "tag-suggestion-active" : ""}`.trim()}
              onMouseDown={(e) => {
                e.preventDefault();
                onChange(s.name);
                setFocused(false);
              }}
              onMouseEnter={() => setActiveIndex(idx)}
            >
              <span>{s.name}</span>
              <span className="tag-suggestion-count">{s.count}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default SectorAutocomplete;
