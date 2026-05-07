import { NavLink } from "react-router-dom";

import { ActivityIcon, BriefcaseIcon, HomeIcon, ListIcon } from "../icons";

interface Props {
  hasActiveRun?: boolean;
  activeRunTitle?: string;
}

export function MobileBottomTabs({ hasActiveRun, activeRunTitle }: Props) {
  return (
    <nav className="mobile-bottom-tabs" aria-label="Hauptnavigation">
      <NavLink
        to="/"
        end
        className={({ isActive }) => `mobile-tab${isActive ? " active" : ""}`}
      >
        <HomeIcon size={22} />
        <span className="mobile-tab-label">Dashboard</span>
      </NavLink>
      <NavLink
        to="/watchlist"
        className={({ isActive }) => `mobile-tab${isActive ? " active" : ""}`}
      >
        <ListIcon size={22} />
        <span className="mobile-tab-label">Watchlist</span>
      </NavLink>
      <NavLink
        to="/jobs"
        className={({ isActive }) => `mobile-tab${isActive ? " active" : ""}`}
      >
        <BriefcaseIcon size={22} />
        <span className="mobile-tab-label">Stellen</span>
      </NavLink>
      <NavLink
        to="/runs"
        className={({ isActive }) => `mobile-tab${isActive ? " active" : ""}`}
      >
        <span className="mobile-tab-icon-wrap">
          <ActivityIcon size={22} />
          {hasActiveRun && (
            <span className="mobile-tab-run-dot" title={activeRunTitle} aria-hidden="true" />
          )}
        </span>
        <span className="mobile-tab-label">Läufe</span>
      </NavLink>
    </nav>
  );
}
