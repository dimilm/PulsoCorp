import { ReactNode, useState } from "react";
import { NavLink } from "react-router-dom";

import { MobileBottomTabs } from "../components/nav/MobileBottomTabs";
import { MobileDrawer } from "../components/nav/MobileDrawer";
import { MobileTopBar } from "../components/nav/MobileTopBar";
import { LogoutButton } from "../components/LogoutButton";
import { ThemeToggle } from "../components/ThemeToggle";
import { useAuth } from "../hooks/useAuth";
import { useIsMobile } from "../hooks/useBreakpoint";
import { useCurrentRun } from "../lib/runProgress";

interface Props {
  children: ReactNode;
}

// Labels for the live-indicator next to the "Aktualisierungen" nav entry.
// Kept short on purpose so the menu stays compact when both pipelines run.
const RUN_TYPE_LABEL = {
  market: "Markt",
  jobs: "Stellen",
} as const;

export function AppLayout({ children }: Props) {
  const { user } = useAuth();
  const isMobile = useIsMobile();
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Both hooks are safe at the top level: the market subscription is shared
  // through CurrentRunProvider (mounted in main.tsx), and the jobs hook only
  // polls while a jobs run is active. When idle they sit on a single fetch.
  const { data: marketRun } = useCurrentRun("market");
  const { data: jobsRun } = useCurrentRun("jobs");
  const activeRunTypes: Array<keyof typeof RUN_TYPE_LABEL> = [];
  if (marketRun && marketRun.phase !== "finished") activeRunTypes.push("market");
  if (jobsRun && jobsRun.phase !== "finished") activeRunTypes.push("jobs");
  const indicatorTitle =
    activeRunTypes.length === 0
      ? undefined
      : `Aktiv: ${activeRunTypes.map((t) => RUN_TYPE_LABEL[t]).join(", ")}`;
  const hasActiveRun = activeRunTypes.length > 0;

  return (
    <>
      {user && isMobile && (
        <>
          <MobileTopBar
            onOpenDrawer={() => setDrawerOpen(true)}
            hasActiveRun={hasActiveRun}
            activeRunTitle={indicatorTitle}
          />
          <MobileDrawer
            open={drawerOpen}
            onClose={() => setDrawerOpen(false)}
            username={user.username}
          />
          <MobileBottomTabs
            hasActiveRun={hasActiveRun}
            activeRunTitle={indicatorTitle}
          />
        </>
      )}
      {user && !isMobile && (
        <nav>
          <NavLink to="/" end className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
            Dashboard
          </NavLink>
          <NavLink to="/watchlist" className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
            Watchlist
          </NavLink>
          <NavLink to="/jobs" className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
            Stellen
          </NavLink>
          <span className="nav-sep" aria-hidden="true" />
          <NavLink
            to="/runs"
            className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
          >
            <span>Aktualisierungen</span>
            {hasActiveRun && (
              <span className="nav-run-indicator" title={indicatorTitle}>
                <span className="nav-run-dot" aria-hidden="true" />
                <span className="nav-run-text">
                  {activeRunTypes.map((t) => RUN_TYPE_LABEL[t]).join(" · ")}
                </span>
              </span>
            )}
          </NavLink>
          <span className="nav-sep" aria-hidden="true" />
          <NavLink to="/settings" className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
            Einstellungen
          </NavLink>
          <span className="nav-user">{user.username}</span>
          <ThemeToggle />
          <LogoutButton />
        </nav>
      )}
      {children}
    </>
  );
}
