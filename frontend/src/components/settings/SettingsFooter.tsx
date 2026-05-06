interface Props {
  feedback: { kind: "ok" | "error"; text: string } | null;
  isDirty: boolean;
  saving: boolean;
  onSave: () => void;
  onDiscard: () => void;
}

export function SettingsFooter({ feedback, isDirty, saving, onSave, onDiscard }: Props) {
  return (
    <footer className="settings-footer">
      {feedback ? (
        <p
          className={`settings-footer-status ${feedback.kind === "ok" ? "is-ok" : "is-error"}`}
          role="alert"
        >
          {feedback.text}
        </p>
      ) : (
        <p className="settings-footer-status">
          {isDirty ? "Du hast ungespeicherte Änderungen." : "Alle Änderungen gespeichert."}
        </p>
      )}
      <div className="settings-footer-actions">
        <button
          type="button"
          className="btn-secondary"
          onClick={onDiscard}
          disabled={!isDirty || saving}
        >
          Verwerfen
        </button>
        <button
          type="button"
          className="btn-primary"
          onClick={onSave}
          disabled={!isDirty || saving}
        >
          {saving ? "Speichere..." : "Speichern"}
        </button>
      </div>
    </footer>
  );
}
