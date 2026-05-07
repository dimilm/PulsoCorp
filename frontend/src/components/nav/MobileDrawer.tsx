import { useEffect, useRef } from "react";
import { NavLink } from "react-router-dom";

import { useFocusTrap } from "../../hooks/useFocusTrap";
import { LogoutButton } from "../LogoutButton";
import { ThemeToggle } from "../ThemeToggle";
import {
  ActivityIcon,
  BriefcaseIcon,
  HomeIcon,
  ListIcon,
  SettingsIcon,
  XIcon,
} from "../icons";

interface Props {
  open: boolean;
  onClose: () => void;
  username?: string;
}

export function MobileDrawer({ open, onClose, username }: Props) {
  const drawerRef = useRef<HTMLDivElement>(null);

  useFocusTrap(drawerRef, open);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="mobile-drawer-backdrop"
        aria-hidden="true"
        onMouseDown={onClose}
      />

      {/* Drawer panel */}
      <div
        ref={drawerRef}
        className="mobile-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Navigation"
      >
        <div className="mobile-drawer-header">
          <span className="mobile-drawer-title">CompanyTracker</span>
          <button
            type="button"
            className="mobile-drawer-close"
            aria-label="Navigation schließen"
            onClick={onClose}
          >
            <XIcon size={20} />
          </button>
        </div>

        <nav className="mobile-drawer-nav">
          <NavLink
            to="/"
            end
            className={({ isActive }) => `mobile-drawer-link${isActive ? " active" : ""}`}
            onClick={onClose}
          >
            <HomeIcon size={18} />
            Dashboard
          </NavLink>
          <NavLink
            to="/watchlist"
            className={({ isActive }) => `mobile-drawer-link${isActive ? " active" : ""}`}
            onClick={onClose}
          >
            <ListIcon size={18} />
            Watchlist
          </NavLink>
          <NavLink
            to="/jobs"
            className={({ isActive }) => `mobile-drawer-link${isActive ? " active" : ""}`}
            onClick={onClose}
          >
            <BriefcaseIcon size={18} />
            Stellen
          </NavLink>
          <NavLink
            to="/runs"
            className={({ isActive }) => `mobile-drawer-link${isActive ? " active" : ""}`}
            onClick={onClose}
          >
            <ActivityIcon size={18} />
            Aktualisierungen
          </NavLink>
          <NavLink
            to="/settings"
            className={({ isActive }) => `mobile-drawer-link${isActive ? " active" : ""}`}
            onClick={onClose}
          >
            <SettingsIcon size={18} />
            Einstellungen
          </NavLink>
        </nav>

        <div className="mobile-drawer-footer">
          {username && (
            <span className="mobile-drawer-user">{username}</span>
          )}
          <ThemeToggle />
          <LogoutButton />
        </div>
      </div>
    </>
  );
}
