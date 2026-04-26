import { useEffect, useMemo, useRef, useState } from "react";

export interface FilterValues {
  query: string;
  sector: string;
  onlyMoat: boolean;
  tags: string[];
}

export const emptyFilters: FilterValues = {
  query: "",
  sector: "",
  onlyMoat: false,
  tags: [],
};

export function buildStocksParams(v: FilterValues) {
  return {
    query: v.query,
    sector: v.sector || undefined,
    burggraben: v.onlyMoat ? true : undefined,
    tags: v.tags.length > 0 ? v.tags.join(",") : undefined,
  };
}

/** Stateful filter form with a 300 ms debounce.
 *
 * Returns both the *current* values (bound to inputs) and the *debounced*
 * values (suitable for query keys). `applyValues` bypasses the debounce so
 * preset selection or URL hydration feels instant.
 *
 * Callers can pass `initial` to seed the form (e.g. from `?q=…` query params)
 * without triggering a debounce on first render.
 */
export function useWatchlistFilters(initial: FilterValues = emptyFilters) {
  const [values, setValues] = useState<FilterValues>(initial);
  const [debounced, setDebounced] = useState<FilterValues>(initial);
  const skipDebounceRef = useRef(false);

  const memoValues = useMemo(() => values, [values]);

  useEffect(() => {
    if (skipDebounceRef.current) {
      skipDebounceRef.current = false;
      return;
    }
    const id = setTimeout(() => setDebounced(memoValues), 300);
    return () => clearTimeout(id);
  }, [memoValues]);

  function patch(partial: Partial<FilterValues>) {
    setValues((prev) => ({ ...prev, ...partial }));
  }

  function applyValues(next: FilterValues) {
    skipDebounceRef.current = true;
    setValues(next);
    setDebounced(next);
  }

  function reset() {
    applyValues(emptyFilters);
  }

  function toggleTag(name: string) {
    setValues((prev) => ({
      ...prev,
      tags: prev.tags.includes(name)
        ? prev.tags.filter((t) => t !== name)
        : [...prev.tags, name],
    }));
  }

  return { values, debounced, patch, applyValues, reset, toggleTag };
}
