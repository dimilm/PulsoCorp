import { useEffect, useState } from "react";

export interface ChartTheme {
  grid: string;
  tick: string;
  line: string;
  tooltipBackground: string;
  tooltipBorder: string;
  tooltipText: string;
}

const FALLBACK: ChartTheme = {
  grid: "#e5e7eb",
  tick: "#6b7280",
  line: "#2563eb",
  tooltipBackground: "#ffffff",
  tooltipBorder: "#e5e7eb",
  tooltipText: "#0f172a",
};

function read(): ChartTheme {
  if (typeof window === "undefined") return FALLBACK;
  const styles = window.getComputedStyle(document.documentElement);
  const get = (name: string, fallback: string) =>
    styles.getPropertyValue(name).trim() || fallback;
  return {
    grid: get("--chart-grid", FALLBACK.grid),
    tick: get("--chart-tick", FALLBACK.tick),
    line: get("--chart-line", FALLBACK.line),
    tooltipBackground: get("--chart-tooltip-bg", FALLBACK.tooltipBackground),
    tooltipBorder: get("--chart-tooltip-border", FALLBACK.tooltipBorder),
    tooltipText: get("--chart-tooltip-text", FALLBACK.tooltipText),
  };
}

/** Reads the live values of the chart-related CSS custom properties so that
 *  recharts (which needs literal SVG colours) follows our design tokens.
 *
 *  Re-evaluates when:
 *    - `<html data-theme>` flips (user toggles light/dark via `useTheme`).
 *    - `(prefers-color-scheme: dark)` changes (user OS theme switches).
 */
export function useChartTheme(): ChartTheme {
  const [theme, setTheme] = useState<ChartTheme>(() => read());

  useEffect(() => {
    function refresh() {
      setTheme(read());
    }

    const observer = new MutationObserver(refresh);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });

    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    mql.addEventListener("change", refresh);

    return () => {
      observer.disconnect();
      mql.removeEventListener("change", refresh);
    };
  }, []);

  return theme;
}
