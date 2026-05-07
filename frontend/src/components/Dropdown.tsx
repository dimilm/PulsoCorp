import { ReactNode, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { useIsMobile } from "../hooks/useBreakpoint";
import { XIcon } from "./icons";

interface DropdownProps {
  trigger: (state: { open: boolean; toggle: () => void }) => ReactNode;
  align?: "left" | "right";
  className?: string;
  menuClassName?: string;
  /** When true (default), renders as a bottom-sheet on mobile instead of
   *  a float menu. Set to false to always use the float popup. */
  mobileSheet?: boolean;
  /** Optional label shown in the bottom-sheet header on mobile */
  mobileSheetTitle?: string;
  children: (close: () => void) => ReactNode;
}

export function Dropdown({
  trigger,
  align = "left",
  className,
  menuClassName,
  mobileSheet = true,
  mobileSheetTitle,
  children,
}: DropdownProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);
  const isMobile = useIsMobile();

  const close = () => setOpen(false);
  const toggle = () => setOpen((prev) => !prev);

  useEffect(() => {
    if (!open) return;
    function onMouseDown(e: MouseEvent) {
      if (isMobile && mobileSheet) return; // handled by sheet backdrop
      if (!ref.current) return;
      if (!ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, isMobile, mobileSheet]);

  // Lock body scroll when bottom-sheet is open
  useEffect(() => {
    if (open && isMobile && mobileSheet) {
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open, isMobile, mobileSheet]);

  const showSheet = open && isMobile && mobileSheet;
  const showFloat = open && !(isMobile && mobileSheet);

  return (
    <div ref={ref} className={`dropdown ${className ?? ""}`.trim()}>
      {trigger({ open, toggle })}
      {showFloat && (
        <div
          className={`dropdown-menu dropdown-menu-${align} ${menuClassName ?? ""}`.trim()}
          role="menu"
        >
          {children(close)}
        </div>
      )}
      {showSheet &&
        createPortal(
          <DropdownSheet title={mobileSheetTitle} onClose={close}>
            {children(close)}
          </DropdownSheet>,
          document.body
        )}
    </div>
  );
}

interface SheetProps {
  title?: string;
  onClose: () => void;
  children: ReactNode;
}

function DropdownSheet({ title, onClose, children }: SheetProps) {
  return (
    <>
      {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
      <div
        className="modal-backdrop modal-backdrop--bottom dropdown-sheet-backdrop"
        onMouseDown={(e) => {
          if (e.target === e.currentTarget) onClose();
        }}
        style={{ zIndex: 55 }}
      >
        <div
          className="modal-card modal-card--bottom-sheet dropdown-sheet"
          role="menu"
          style={{ zIndex: 56 }}
        >
          <div className="modal-drag-handle" aria-hidden="true" />
          {title && (
            <div className="dropdown-sheet-header">
              <span className="dropdown-sheet-title">{title}</span>
              <button
                type="button"
                className="modal-close"
                aria-label="Schließen"
                onClick={onClose}
              >
                <XIcon size={16} />
              </button>
            </div>
          )}
          <div className="dropdown-sheet-items">
            {children}
          </div>
        </div>
      </div>
    </>
  );
}

interface DropdownItemProps {
  onSelect: () => void;
  danger?: boolean;
  disabled?: boolean;
  children: ReactNode;
}

export function DropdownItem({ onSelect, danger, disabled, children }: DropdownItemProps) {
  return (
    <button
      type="button"
      role="menuitem"
      disabled={disabled}
      className={`dropdown-item ${danger ? "danger" : ""}`.trim()}
      onClick={onSelect}
    >
      {children}
    </button>
  );
}

export function DropdownSeparator() {
  return <div className="dropdown-separator" role="separator" />;
}
