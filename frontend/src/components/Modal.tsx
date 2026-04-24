import { ReactNode, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { XIcon } from "./icons";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  closeOnBackdrop?: boolean;
}

export function Modal({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
  closeOnBackdrop = true,
}: ModalProps) {
  const cardRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  useEffect(() => {
    if (!open || !cardRef.current) return;
    const focusable = cardRef.current.querySelector<HTMLElement>(
      'input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), button:not([disabled])'
    );
    focusable?.focus();
  }, [open]);

  if (!open) return null;

  return createPortal(
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (closeOnBackdrop && e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        ref={cardRef}
      >
        <header className="modal-header">
          <div className="modal-header-text">
            <h3>{title}</h3>
            {subtitle && <div className="modal-subtitle">{subtitle}</div>}
          </div>
          <button
            type="button"
            className="modal-close"
            aria-label="Schließen"
            onClick={onClose}
          >
            <XIcon size={16} />
          </button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer className="modal-footer">{footer}</footer>}
      </div>
    </div>,
    document.body
  );
}

export default Modal;
