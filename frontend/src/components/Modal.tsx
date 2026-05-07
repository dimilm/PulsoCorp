import { ReactNode, useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";

import { useFocusTrap } from "../hooks/useFocusTrap";
import { XIcon } from "./icons";

/** 'center' is the default modal positioned in the upper-center of the
 *  viewport. 'bottomSheet' slides up from the bottom edge — ideal on mobile. */
export type ModalVariant = "center" | "bottomSheet";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  closeOnBackdrop?: boolean;
  variant?: ModalVariant;
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
  variant = "center",
}: ModalProps) {
  if (!open) return null;
  return createPortal(
    <ModalShell
      onClose={onClose}
      title={title}
      subtitle={subtitle}
      footer={footer}
      closeOnBackdrop={closeOnBackdrop}
      variant={variant}
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
  variant: ModalVariant;
  children: ReactNode;
}

function ModalShell({ onClose, title, subtitle, footer, closeOnBackdrop, variant, children }: ShellProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const subtitleId = useId();

  useEsc(onClose);
  useBodyScrollLock();
  useFocusTrap(cardRef, true);

  const isSheet = variant === "bottomSheet";

  return (
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions
    <div
      className={isSheet ? "modal-backdrop modal-backdrop--bottom" : "modal-backdrop"}
      onMouseDown={(e) => {
        if (closeOnBackdrop && e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className={isSheet ? "modal-card modal-card--bottom-sheet" : "modal-card"}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={subtitle ? subtitleId : undefined}
        ref={cardRef}
        tabIndex={-1}
      >
        {isSheet && <div className="modal-drag-handle" aria-hidden="true" />}
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
