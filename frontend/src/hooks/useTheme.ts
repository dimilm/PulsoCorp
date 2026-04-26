import { useCallback, useEffect, useState } from "react";

export type ThemeChoice = "light" | "dark" | "auto";

const STORAGE_KEY = "ct-theme";

function readStored(): ThemeChoice {
  if (typeof localStorage === "undefined") return "auto";
  const v = localStorage.getItem(STORAGE_KEY);
  if (v === "light" || v === "dark") return v;
  return "auto";
}

function applyTheme(choice: ThemeChoice) {
  const root = document.documentElement;
  if (choice === "auto") {
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", choice);
  }
}

/** Tri-state theme controller: "auto" follows the OS preference, "light" /
 *  "dark" pin a fixed mode. The choice is mirrored onto `<html data-theme>`
 *  (consumed by the CSS token overrides) and persisted in localStorage so it
 *  survives reloads.
 */
export function useTheme() {
  const [theme, setThemeState] = useState<ThemeChoice>(() => readStored());

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const setTheme = useCallback((next: ThemeChoice) => {
    if (next === "auto") {
      localStorage.removeItem(STORAGE_KEY);
    } else {
      localStorage.setItem(STORAGE_KEY, next);
    }
    setThemeState(next);
  }, []);

  const cycleTheme = useCallback(() => {
    setTheme(theme === "auto" ? "light" : theme === "light" ? "dark" : "auto");
  }, [theme, setTheme]);

  return { theme, setTheme, cycleTheme };
}
