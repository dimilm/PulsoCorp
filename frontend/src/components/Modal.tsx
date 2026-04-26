import { ReactNode, useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";

import { useFocusTrap } from "../hooks/useFocusTrap";
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

/** Top-level Modal component. Renders into a portal so it can escape ancestor
 *  stacking contexts. Side effects (Esc key, body scroll lock, focus trap)
 *  only run while the modal is mounted to avoid leaking listeners. */
export function Modal({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
  closeOnBackdrop = true,
}: ModalProps) {
  if (!open) return null;
  return createPortal(
    <ModalShell
      onClose={onClose}
      title={title}
      subtitle={subtitle}
      footer={footer}
      closeOnBackdrop={closeOnBackdrop}
    >
      {children}
    </ModalShell>,
    document.body
  );
}

interface ShellProps {
  onClose: () => void;
  title: string;
  subtitle?: ReactNode;
  footer?: ReactNode;
  closeOnBackdrop: boolean;
  children: ReactNode;
}

function ModalShell({ onClose, title, subtitle, footer, closeOnBackdrop, children }: ShellProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const subtitleId = useId();

  useEsc(onClose);
  useBodyScrollLock();
  useFocusTrap(cardRef, true);

  return (
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
        aria-labelledby={titleId}
        aria-describedby={subtitle ? subtitleId : undefined}
        ref={cardRef}
        tabIndex={-1}
      >
        <header className="modal-header">
          <div className="modal-header-text">
            <h3 id={titleId}>{title}</h3>
            {subtitle && (
              <div id={subtitleId} className="modal-subtitle">
                {subtitle}
              </div>
            )}
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
    </div>
  );
}

function useEsc(onClose: () => void) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
}

function useBodyScrollLock() {
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);
}

export default Modal;
