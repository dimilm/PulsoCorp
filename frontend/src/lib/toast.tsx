import { ReactNode, useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { XIcon } from "../components/icons";

export type ToastVariant = "info" | "success" | "warning" | "error";

export interface ToastOptions {
  message: ReactNode;
  variant?: ToastVariant;
  /** Auto-dismiss after this many ms. Use 0 for sticky toasts (e.g. errors
   *  that require an explicit dismissal). Defaults to 4500 ms (success/info)
   *  or 6500 ms (warning/error). */
  duration?: number;
  title?: string;
}

interface Toast extends ToastOptions {
  id: number;
}

type Listener = (toasts: Toast[]) => void;

let nextId = 1;
let listeners: Listener[] = [];
let queue: Toast[] = [];

function emit() {
  const snapshot = [...queue];
  for (const listener of listeners) listener(snapshot);
}

function dismiss(id: number) {
  queue = queue.filter((t) => t.id !== id);
  emit();
}

function show(options: ToastOptions): number {
  const variant = options.variant ?? "info";
  const defaultDuration = variant === "error" || variant === "warning" ? 6500 : 4500;
  const toast: Toast = {
    id: nextId++,
    variant,
    duration: options.duration ?? defaultDuration,
    ...options,
  };
  queue = [...queue, toast];
  emit();
  if (toast.duration && toast.duration > 0) {
    window.setTimeout(() => dismiss(toast.id), toast.duration);
  }
  return toast.id;
}

/** Imperative toast API used outside the React tree (e.g. inside `catch`
 *  blocks of mutations). Mount `<ToastHost />` once near the app root. */
export const toast = {
  show,
  dismiss,
  info: (message: ReactNode, options?: Omit<ToastOptions, "message" | "variant">) =>
    show({ ...options, message, variant: "info" }),
  success: (message: ReactNode, options?: Omit<ToastOptions, "message" | "variant">) =>
    show({ ...options, message, variant: "success" }),
  warning: (message: ReactNode, options?: Omit<ToastOptions, "message" | "variant">) =>
    show({ ...options, message, variant: "warning" }),
  error: (message: ReactNode, options?: Omit<ToastOptions, "message" | "variant">) =>
    show({ ...options, message, variant: "error" }),
};

export function ToastHost() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    listeners.push(setToasts);
    return () => {
      listeners = listeners.filter((l) => l !== setToasts);
    };
  }, []);

  if (toasts.length === 0) return null;

  return createPortal(
    <div className="toast-stack" role="region" aria-label="Benachrichtigungen">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
      ))}
    </div>,
    document.body
  );
}

function ToastItem({ toast: t, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  return (
    <div
      className={`toast toast-${t.variant ?? "info"}`}
      role={t.variant === "error" ? "alert" : "status"}
      aria-live={t.variant === "error" ? "assertive" : "polite"}
    >
      <div className="toast-body">
        {t.title && <div className="toast-title">{t.title}</div>}
        <div className="toast-message">{t.message}</div>
      </div>
      <button
        type="button"
        className="toast-dismiss"
        aria-label="Schließen"
        onClick={onDismiss}
      >
        <XIcon size={14} />
      </button>
    </div>
  );
}
