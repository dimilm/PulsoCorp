import { Spinner } from "../components/Spinner";
import { AiProviderCard } from "../components/settings/AiProviderCard";
import { ColorThresholdsCard } from "../components/settings/ColorThresholdsCard";
import { ExportCard } from "../components/settings/ExportCard";
import { JobsScheduleCard } from "../components/settings/JobsScheduleCard";
import { SettingsFooter } from "../components/settings/SettingsFooter";
import { UpdateScheduleCard } from "../components/settings/UpdateScheduleCard";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useSettings } from "../hooks/useSettings";

export function SettingsPage() {
  useDocumentTitle("Einstellungen");
  const s = useSettings();

  if (s.loadError) {
    return (
      <div className="page">
        <p className="form-banner-error" role="alert">{s.loadError}</p>
      </div>
    );
  }

  if (!s.settings) {
    return (
      <div className="page">
        <Spinner label="Lade Einstellungen..." />
      </div>
    );
  }

  return (
    <div className="page settings-page">
      <div className="page-header">
        <div className="page-header-title">
          <h2>Einstellungen</h2>
        </div>
      </div>

      <div className="settings-grid">
        <UpdateScheduleCard
          settings={s.settings}
          onChange={(patch) => s.setSettings({ ...s.settings!, ...patch })}
        />
        <JobsScheduleCard
          settings={s.settings}
          onChange={(patch) => s.setSettings({ ...s.settings!, ...patch })}
        />
        <AiProviderCard
          settings={s.settings}
          onChange={(patch) => s.setSettings({ ...s.settings!, ...patch })}
          apiKey={s.apiKey}
          setApiKey={s.setApiKey}
          editKey={s.editKey}
          setEditKey={s.setEditKey}
          testing={s.testing}
          testResult={s.testResult}
          setTestResult={s.setTestResult}
          isDirty={s.isDirty}
          onTestConnection={() => void s.testConnection()}
        />
        <ExportCard
          exportingCsv={s.exportingCsv}
          exportingSeed={s.exportingSeed}
          exportingJobHistory={s.exportingJobHistory}
          importingJobHistory={s.importingJobHistory}
          onDownloadCsv={() => void s.downloadCsv()}
          onDownloadSeed={() => void s.downloadSeed()}
          onDownloadJobHistory={() => void s.downloadJobHistory()}
          onUploadJobHistory={(file) => void s.uploadJobHistory(file)}
        />
        <ColorThresholdsCard thresholds={s.thresholds} onChange={s.setThresholds} />
      </div>

      <SettingsFooter
        feedback={s.feedback}
        isDirty={s.isDirty}
        saving={s.saving}
        onSave={() => void s.save()}
        onDiscard={s.discardChanges}
      />
    </div>
  );
}
