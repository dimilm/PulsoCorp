import { useTheme, type ThemeChoice } from "../hooks/useTheme";

const ICON: Record<ThemeChoice, string> = {
  auto: "◐",
  light: "☀",
  dark: "☾",
};

const LABEL: Record<ThemeChoice, string> = {
  auto: "Theme: System",
  light: "Theme: Hell",
  dark: "Theme: Dunkel",
};

const NEXT: Record<ThemeChoice, ThemeChoice> = {
  auto: "light",
  light: "dark",
  dark: "auto",
};

export function ThemeToggle() {
  const { theme, cycleTheme } = useTheme();
  return (
    <button
      type="button"
      className="nav-theme-toggle"
      onClick={cycleTheme}
      title={`${LABEL[theme]} (klick wechselt zu ${LABEL[NEXT[theme]].toLowerCase()})`}
      aria-label={LABEL[theme]}
    >
      <span aria-hidden="true">{ICON[theme]}</span>
    </button>
  );
}
