import { useState } from "react";
import { api } from "../../api/client";
import { extractApiError } from "../../lib/apiError";

export function ChangePasswordCard() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    if (newPassword !== confirmPassword) {
      setError("Die neuen Passwörter stimmen nicht überein");
      return;
    }

    setSubmitting(true);
    try {
      await api.post("/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setSuccess(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(extractApiError(err, "Passwort konnte nicht geändert werden"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="settings-card">
      <header className="settings-card-header">
        <h3>Passwort ändern</h3>
      </header>

      <form onSubmit={(e) => void handleSubmit(e)}>
        <div className="field">
          <label htmlFor="cp-current">Aktuelles Passwort</label>
          <input
            id="cp-current"
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            autoComplete="current-password"
          />
        </div>

        <div className="field">
          <label htmlFor="cp-new">Neues Passwort</label>
          <input
            id="cp-new"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            autoComplete="new-password"
          />
        </div>

        <div className="field">
          <label htmlFor="cp-confirm">Neues Passwort bestätigen</label>
          <input
            id="cp-confirm"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            autoComplete="new-password"
          />
        </div>

        {success && (
          <p className="form-banner-success" role="status">
            Passwort erfolgreich geändert.
          </p>
        )}

        {error && (
          <p className="form-banner-error" role="alert">
            {error}
          </p>
        )}

        <button type="submit" className="btn-primary" disabled={submitting}>
          {submitting ? "Wird gespeichert..." : "Passwort ändern"}
        </button>
      </form>
    </section>
  );
}
