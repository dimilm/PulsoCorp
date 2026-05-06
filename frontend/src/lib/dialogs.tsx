import { FormEvent, ReactNode, useEffect, useState } from "react";

import { Modal } from "../components/Modal";

// Imperative dialog API to replace the native window.confirm / window.prompt /
// window.alert calls. Mount <DialogHost /> once near the root, then call:
//
//   const ok = await confirm({ message: "..." });
//   const name = await prompt({ message: "..." });
//   await alertDialog({ message: "..." });
//
// Each call returns a Promise that resolves once the user picks an option.
// The implementation uses a tiny singleton bus so the API stays as ergonomic
// as the native counterparts – there is no extra context boilerplate at the
// call site.

export interface ConfirmOptions {
  title?: string;
  message: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
}

export interface PromptOptions {
  title?: string;
  message?: ReactNode;
  defaultValue?: string;
  placeholder?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  validate?: (value: string) => string | null;
}

export interface AlertOptions {
  title?: string;
  message: ReactNode;
  confirmLabel?: string;
  variant?: "info" | "warning" | "error" | "success";
}

type Pending =
  | { kind: "confirm"; opts: ConfirmOptions; resolve: (v: boolean) => void }
  | { kind: "prompt"; opts: PromptOptions; resolve: (v: string | null) => void }
  | { kind: "alert"; opts: AlertOptions; resolve: () => void };

let setPendingFn: ((next: Pending | null) => void) | null = null;

function enqueue(p: Pending) {
  if (!setPendingFn) {
    // DialogHost was not mounted. Fall back to native dialogs so destructive
    // actions are never silently confirmed.
    if (p.kind === "confirm") p.resolve(window.confirm(toString(p.opts.message)));
    else if (p.kind === "prompt")
      p.resolve(window.prompt(toString(p.opts.message ?? "") || "Eingabe", p.opts.defaultValue ?? ""));
    else {
      window.alert(toString(p.opts.message));
      p.resolve();
    }
    return;
  }
  setPendingFn(p);
}

function toString(node: ReactNode): string {
  if (typeof node === "string") return node;
  if (typeof node === "number") return String(node);
  return "";
}

export function confirm(opts: ConfirmOptions): Promise<boolean> {
  return new Promise((resolve) => enqueue({ kind: "confirm", opts, resolve }));
}

export function prompt(opts: PromptOptions): Promise<string | null> {
  return new Promise((resolve) => enqueue({ kind: "prompt", opts, resolve }));
}

// Renamed to avoid shadowing the global `alert`. Use `import { alertDialog }`
// at the call site.
export function alertDialog(opts: AlertOptions): Promise<void> {
  return new Promise((resolve) => enqueue({ kind: "alert", opts, resolve }));
}

export function DialogHost() {
  const [pending, setPending] = useState<Pending | null>(null);

  useEffect(() => {
    setPendingFn = setPending;
    return () => {
      setPendingFn = null;
    };
  }, []);

  if (!pending) return null;

  if (pending.kind === "confirm") {
    return (
      <ConfirmDialog
        opts={pending.opts}
        onResolve={(value) => {
          setPending(null);
          pending.resolve(value);
        }}
      />
    );
  }

  if (pending.kind === "prompt") {
    return (
      <PromptDialog
        opts={pending.opts}
        onResolve={(value) => {
          setPending(null);
          pending.resolve(value);
        }}
      />
    );
  }

  return (
    <AlertDialog
      opts={pending.opts}
      onResolve={() => {
        setPending(null);
        pending.resolve();
      }}
    />
  );
}

function ConfirmDialog({
  opts,
  onResolve,
}: {
  opts: ConfirmOptions;
  onResolve: (value: boolean) => void;
}) {
  const confirmLabel = opts.confirmLabel ?? (opts.destructive ? "Löschen" : "Bestätigen");
  const cancelLabel = opts.cancelLabel ?? "Abbrechen";
  return (
    <Modal
      open
      onClose={() => onResolve(false)}
      title={opts.title ?? "Bitte bestätigen"}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={() => onResolve(false)}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={opts.destructive ? "btn-danger" : "btn-primary"}
            onClick={() => onResolve(true)}
            // eslint-disable-next-line jsx-a11y/no-autofocus
            autoFocus
          >
            {confirmLabel}
          </button>
        </>
      }
    >
      <p className="dialog-message">{opts.message}</p>
    </Modal>
  );
}

function PromptDialog({
  opts,
  onResolve,
}: {
  opts: PromptOptions;
  onResolve: (value: string | null) => void;
}) {
  const [value, setValue] = useState(opts.defaultValue ?? "");
  const [error, setError] = useState<string | null>(null);

  function submit(e: FormEvent) {
    e.preventDefault();
    const validation = opts.validate?.(value) ?? null;
    if (validation) {
      setError(validation);
      return;
    }
    onResolve(value);
  }

  return (
    <Modal
      open
      onClose={() => onResolve(null)}
      title={opts.title ?? "Eingabe"}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={() => onResolve(null)}>
            {opts.cancelLabel ?? "Abbrechen"}
          </button>
          <button type="submit" form="dialog-prompt-form" className="btn-primary">
            {opts.confirmLabel ?? "Bestätigen"}
          </button>
        </>
      }
    >
      <form id="dialog-prompt-form" onSubmit={submit} className="dialog-prompt-form">
        {opts.message && <p className="dialog-message">{opts.message}</p>}
        <input
          type="text"
          value={value}
          placeholder={opts.placeholder}
          onChange={(e) => {
            setValue(e.target.value);
            if (error) setError(null);
          }}
          // eslint-disable-next-line jsx-a11y/no-autofocus
          autoFocus
          className="dialog-prompt-input"
        />
        {error && (
          <p className="form-banner-error" role="alert">
            {error}
          </p>
        )}
      </form>
    </Modal>
  );
}

function AlertDialog({
  opts,
  onResolve,
}: {
  opts: AlertOptions;
  onResolve: () => void;
}) {
  const variant = opts.variant ?? "info";
  return (
    <Modal
      open
      onClose={onResolve}
      title={opts.title ?? defaultAlertTitle(variant)}
      footer={
        <button type="button" className="btn-primary" onClick={onResolve}
          // eslint-disable-next-line jsx-a11y/no-autofocus
          autoFocus>
          {opts.confirmLabel ?? "OK"}
        </button>
      }
    >
      <div className={`dialog-message dialog-alert dialog-alert-${variant}`}>{opts.message}</div>
    </Modal>
  );
}

function defaultAlertTitle(variant: AlertOptions["variant"]): string {
  switch (variant) {
    case "warning":
      return "Achtung";
    case "error":
      return "Fehler";
    case "success":
      return "Erfolg";
    default:
      return "Hinweis";
  }
}
