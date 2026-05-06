import { ColorThresholds, defaultThresholds } from "../../lib/colorRules";

interface Props {
  thresholds: ColorThresholds;
  onChange: (next: ColorThresholds) => void;
}

export function ColorThresholdsCard({ thresholds, onChange }: Props) {
  function patch(partial: Partial<ColorThresholds>) {
    onChange({ ...thresholds, ...partial });
  }

  return (
    <section className="settings-card">
      <header className="settings-card-header">
        <h3>Farb-Schwellen</h3>
        <p className="settings-card-subtitle">
          Ab welchen Werten Tabellen-Spalten farbig hervorgehoben werden. Nur in deinem Browser gespeichert.
        </p>
      </header>

      <div className="field">
        <label htmlFor="th-gain">Tagesgewinn — ab welchem % wird die Spalte grün?</label>
        <input
          id="th-gain"
          type="number"
          step="0.1"
          value={thresholds.strongGainPct}
          onChange={(e) => patch({ strongGainPct: Number(e.target.value) })}
        />
        <span className="helper">Standard: 4 (z. B. +4,5 % wird grün eingefärbt).</span>
      </div>

      <div className="field">
        <label htmlFor="th-loss">Tagesverlust — ab welchem % wird die Spalte rot?</label>
        <input
          id="th-loss"
          type="number"
          step="0.1"
          value={thresholds.strongLossPct}
          onChange={(e) => patch({ strongLossPct: Number(e.target.value) })}
        />
        <span className="helper">Standard: −4 (negative Zahl). Werte unter dieser Schwelle werden rot.</span>
      </div>

      <div className="field">
        <label htmlFor="th-target">Analysten-Kursziel — ab wie viel % über Kurs türkis?</label>
        <input
          id="th-target"
          type="number"
          step="0.1"
          value={thresholds.targetDistancePct}
          onChange={(e) => patch({ targetDistancePct: Number(e.target.value) })}
        />
        <span className="helper">Standard: 10 (Kursziel ≥ 10 % über aktuellem Kurs).</span>
      </div>

      <div className="field">
        <label htmlFor="th-div">Hohe Dividendenrendite — ab welchem % türkis?</label>
        <input
          id="th-div"
          type="number"
          step="0.1"
          value={thresholds.highDividendPct}
          onChange={(e) => patch({ highDividendPct: Number(e.target.value) })}
        />
        <span className="helper">Standard: 4 (Dividendenrendite ≥ 4 %).</span>
      </div>

      <div className="settings-row">
        <button type="button" className="btn-link" onClick={() => onChange(defaultThresholds)}>
          Auf Standard zurücksetzen
        </button>
      </div>
    </section>
  );
}
