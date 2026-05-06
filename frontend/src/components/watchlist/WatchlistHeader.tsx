import { ChevronDownIcon, PlusIcon } from "../icons";
import { Dropdown, DropdownItem } from "../Dropdown";

interface Props {
  stockCount: number;
  isRunActive: boolean;
  onTriggerAll: () => void;
  onImportCsv: () => void;
  onExportCsv: () => void;
  onOpenCreate: () => void;
}

export function WatchlistHeader({
  stockCount,
  isRunActive,
  onTriggerAll,
  onImportCsv,
  onExportCsv,
  onOpenCreate,
}: Props) {
  return (
    <header className="page-header">
      <div className="page-header-title">
        <h2>
          Watchlist
          <span className="muted-count"> ({stockCount})</span>
        </h2>
      </div>
      <div className="page-header-actions">
        <Dropdown
          align="right"
          trigger={({ toggle, open }) => (
            <button
              type="button"
              className={`btn-secondary with-caret ${open ? "is-open" : ""}`.trim()}
              onClick={toggle}
              aria-haspopup="menu"
              aria-expanded={open}
            >
              Daten
              <ChevronDownIcon />
            </button>
          )}
        >
          {(close) => (
            <>
              <DropdownItem
                disabled={isRunActive}
                onSelect={() => {
                  close();
                  onTriggerAll();
                }}
              >
                {isRunActive ? "Aktualisierung läuft…" : "Alle aktualisieren"}
              </DropdownItem>
              <DropdownItem
                onSelect={() => {
                  close();
                  onImportCsv();
                }}
              >
                CSV importieren
              </DropdownItem>
              <DropdownItem
                onSelect={() => {
                  close();
                  onExportCsv();
                }}
              >
                CSV exportieren
              </DropdownItem>
            </>
          )}
        </Dropdown>
        <button type="button" className="btn-primary with-icon" onClick={onOpenCreate}>
          <PlusIcon />
          Unternehmen
        </button>
      </div>
    </header>
  );
}
