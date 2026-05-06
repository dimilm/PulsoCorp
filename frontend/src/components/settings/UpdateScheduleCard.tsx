import { Link } from "react-router-dom";
import { SettingsState } from "../../hooks/useSettings";

function pad2(n: number): string {
  return n.toString().padStart(2, "0");
}

function timeToString(hour: number, minute: number): string {
  return `${pad2(hour)}:${pad2(minute)}`;
}

function parseTime(value: string): { hour: number; minute: number } | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(value);
  if (!match) return null;
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (Number.isNaN(hour) || Number.isNaN(minute)) return null;
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return null;
  return { hour, minute };
}

interface Props {
  settings: SettingsState;
  onChange: (patch: Partial<SettingsState>) => void;
}

export function UpdateScheduleCard({ settings, onChange }: Props) {
  const nextRunLabel = `${pad2(settings.update_hour)}:${pad2(settings.update_minute)}${
    settings.update_weekends ? "" : " (an Werktagen)"
  }`;

  return (
    <section className="settings-card">
      <header className="settings-card-header">
        <h3>Automatisches Update</h3>
        <p className="settings-card-subtitle">
          Wann werden Kurse, Kennzahlen und KI-Bewertungen für alle Aktien automatisch aktualisiert?
        </p>
      </header>

      <div className="field">
        <label htmlFor="setting-time">Lauf-Uhrzeit</label>
        <input
          id="setting-time"
          type="time"
          value={timeToString(settings.update_hour, settings.update_minute)}
          onChange={(e) => {
            const parsed = parseTime(e.target.value);
            if (parsed) onChange({ update_hour: parsed.hour, update_minute: parsed.minute });
          }}
        />
        <span className="helper">
          Standard 22:30 (lokale Zeit), nach US-Börsenschluss. Lauf-Historie unter{" "}
          <Link to="/runs" className="settings-info-link">Läufe</Link>.
        </span>
      </div>

      {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
      <label className="toggle-row">
        <input
          type="checkbox"
          checked={settings.update_weekends}
          onChange={(e) => onChange({ update_weekends: e.target.checked })}
        />
        <span className="toggle-switch" aria-hidden="true">
          <span className="toggle-knob" />
        </span>
        <span className="toggle-text">
          <span className="toggle-title">Auch am Wochenende laufen</span>
          <span className="toggle-help">
            Standardmäßig aus, weil die Börsen am Wochenende geschlossen sind.
          </span>
        </span>
      </label>

      <div className="settings-info-line">
        <span>
          Nächster geplanter Lauf: <strong>{nextRunLabel}</strong>
        </span>
        <Link to="/runs" className="settings-info-link">→ Lauf-Historie öffnen</Link>
      </div>
    </section>
  );
}
