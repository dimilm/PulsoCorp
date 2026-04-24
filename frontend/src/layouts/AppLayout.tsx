import { ReactNode } from "react";
import { NavLink } from "react-router-dom";

import { LogoutButton } from "../components/LogoutButton";
import type { AuthUser } from "../hooks/useAuth";

interface Props {
  user: AuthUser;
  onLoggedOut: () => void;
  children: ReactNode;
}

export function AppLayout({ user, onLoggedOut, children }: Props) {
  return (
    <>
      {user && (
        <nav>
          <NavLink to="/" end className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
            Dashboard
          </NavLink>
          <NavLink to="/watchlist" className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
            Watchlist
          </NavLink>
          <NavLink to="/runs" className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
            Runs
          </NavLink>
          <NavLink to="/settings" className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
            Settings
          </NavLink>
          <span className="nav-user">{user.username}</span>
          <LogoutButton onLoggedOut={onLoggedOut} />
        </nav>
      )}
      {children}
    </>
  );
}
