import { ReactNode, useEffect, useRef, useState } from "react";

interface DropdownProps {
  trigger: (state: { open: boolean; toggle: () => void }) => ReactNode;
  align?: "left" | "right";
  className?: string;
  menuClassName?: string;
  children: (close: () => void) => ReactNode;
}

export function Dropdown({ trigger, align = "left", className, menuClassName, children }: DropdownProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  const close = () => setOpen(false);
  const toggle = () => setOpen((prev) => !prev);

  useEffect(() => {
    if (!open) return;
    function onMouseDown(e: MouseEvent) {
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
  }, [open]);

  return (
    <div ref={ref} className={`dropdown ${className ?? ""}`.trim()}>
      {trigger({ open, toggle })}
      {open && (
        <div
          className={`dropdown-menu dropdown-menu-${align} ${menuClassName ?? ""}`.trim()}
          role="menu"
        >
          {children(close)}
        </div>
      )}
    </div>
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
