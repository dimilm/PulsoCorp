import { useRef } from "react";

interface Props {
  exportingCsv: boolean;
  exportingSeed: boolean;
  exportingJobHistory: boolean;
  importingJobHistory: boolean;
  onDownloadCsv: () => void;
  onDownloadSeed: () => void;
  onDownloadJobHistory: () => void;
  onUploadJobHistory: (file: File) => void;
}

export function ExportCard({
  exportingCsv,
  exportingSeed,
  exportingJobHistory,
  importingJobHistory,
  onDownloadCsv,
  onDownloadSeed,
  onDownloadJobHistory,
  onUploadJobHistory,
}: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <section className="settings-card">
      <header className="settings-card-header">
        <h3>Daten exportieren / importieren</h3>
        <p className="settings-card-subtitle">
          Watchlist als CSV für Excel, Seed-Datei für Backup, oder Job-Historie exportieren und importieren.
        </p>
      </header>

      <div className="settings-export-row">
        <span className="settings-export-title">Watchlist als CSV</span>
        <span className="helper">
          Aktuelle Aktien mit Kurs, Empfehlung und investiertem Kapital — direkt in Excel öffnen.
        </span>
        <div className="settings-export-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={onDownloadCsv}
            disabled={exportingCsv}
          >
            {exportingCsv ? "Exportiere..." : "CSV herunterladen"}
          </button>
        </div>
      </div>

      <div className="settings-export-row">
        <span className="settings-export-title">Seed-Datei (stocks.seed.json)</span>
        <span className="helper">
          Lädt den aktuellen DB-Stand als <code>stocks.seed.json</code> herunter. Datei in{" "}
          <code>backend/app/seed/</code> ablegen, um den Seed im Source zu aktualisieren.
        </span>
        <div className="settings-export-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={onDownloadSeed}
            disabled={exportingSeed}
          >
            {exportingSeed ? "Exportiere..." : "Seed herunterladen"}
          </button>
        </div>
      </div>

      <div className="settings-export-row">
        <span className="settings-export-title">Job-Historie (job-history.csv)</span>
        <span className="helper">
          Exportiert alle gespeicherten Stellenzahlen aller Quellen als CSV. Dieselbe Datei kann
          nach manueller Bearbeitung wieder hochgeladen werden — bestehende Werte werden nicht
          überschrieben, nur fehlende Tage eingefügt.
        </span>
        <div className="settings-export-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={onDownloadJobHistory}
            disabled={exportingJobHistory || importingJobHistory}
          >
            {exportingJobHistory ? "Exportiere..." : "Job-Historie exportieren"}
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => fileInputRef.current?.click()}
            disabled={importingJobHistory || exportingJobHistory}
          >
            {importingJobHistory ? "Importiere..." : "Job-Historie importieren"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            style={{ display: "none" }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) {
                onUploadJobHistory(file);
                e.target.value = "";
              }
            }}
          />
        </div>
      </div>
    </section>
  );
}
