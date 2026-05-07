import { MenuIcon } from "../icons";

interface Props {
  onOpenDrawer: () => void;
  hasActiveRun?: boolean;
  activeRunTitle?: string;
}

export function MobileTopBar({ onOpenDrawer, hasActiveRun, activeRunTitle }: Props) {
  return (
    <header className="mobile-top-bar">
      <button
        type="button"
        className="mobile-top-bar-menu"
        aria-label="Navigation öffnen"
        onClick={onOpenDrawer}
      >
        <MenuIcon size={22} />
        {hasActiveRun && (
          <span className="mobile-top-bar-run-dot" title={activeRunTitle} aria-hidden="true" />
        )}
      </button>
      <span className="mobile-top-bar-title">CompanyTracker</span>
    </header>
  );
}
