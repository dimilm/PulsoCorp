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

export function JobsScheduleCard({ settings, onChange }: Props) {
  return (
    <section className="settings-card">
      <header className="settings-card-header">
        <h3>Karriereportal-Scrape</h3>
        <p className="settings-card-subtitle">
          Wann werden offene Stellen der konfigurierten Karriereportale automatisch erfasst?
        </p>
      </header>

      <div className="field">
        <label htmlFor="setting-jobs-time">Lauf-Uhrzeit</label>
        <input
          id="setting-jobs-time"
          type="time"
          value={timeToString(settings.jobs_update_hour, settings.jobs_update_minute)}
          onChange={(e) => {
            const parsed = parseTime(e.target.value);
            if (parsed)
              onChange({ jobs_update_hour: parsed.hour, jobs_update_minute: parsed.minute });
          }}
        />
        <span className="helper">
          Standard 02:00 (lokale Zeit), getrennt vom Marktdaten-Update. Quellen verwalten unter{" "}
          <Link to="/jobs" className="settings-info-link">Jobs</Link>.
        </span>
      </div>

      {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
      <label className="toggle-row">
        <input
          type="checkbox"
          checked={settings.jobs_enabled}
          onChange={(e) => onChange({ jobs_enabled: e.target.checked })}
        />
        <span className="toggle-switch" aria-hidden="true">
          <span className="toggle-knob" />
        </span>
        <span className="toggle-text">
          <span className="toggle-title">Automatischer Scrape aktiviert</span>
          <span className="toggle-help">
            Bei deaktivierter Option läuft der Cron nicht. Manuelles &quot;Alle aktualisieren&quot; funktioniert weiterhin.
          </span>
        </span>
      </label>
    </section>
  );
}
