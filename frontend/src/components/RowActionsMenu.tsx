import { Stock } from "../types";
import { Dropdown, DropdownItem, DropdownSeparator } from "./Dropdown";
import { KebabIcon } from "./icons";

interface Props {
  stock: Stock;
  onRefresh: (isin: string) => Promise<void>;
  onEvaluate: (isin: string) => Promise<void>;
  onAiPreview: (isin: string) => Promise<void>;
  onToggleLock: (isin: string, field: string, locked: boolean) => Promise<void>;
  onEdit: (stock: Stock) => void;
  onDelete: (stock: Stock) => Promise<void>;
}

export default function RowActionsMenu({
  stock,
  onRefresh,
  onEvaluate,
  onAiPreview,
  onToggleLock,
  onEdit,
  onDelete,
}: Props) {
  const recLocked = !!stock.field_locks?.recommendation;

  return (
    <Dropdown
      align="right"
      className="row-actions"
      trigger={({ toggle, open }) => (
        <button
          type="button"
          className={`kebab-button ${open ? "is-open" : ""}`.trim()}
          aria-label="Aktionen"
          aria-haspopup="menu"
          aria-expanded={open}
          onClick={toggle}
        >
          <KebabIcon size={18} />
        </button>
      )}
    >
      {(close) => (
        <>
          <DropdownItem
            onSelect={() => {
              close();
              void onRefresh(stock.isin);
            }}
          >
            Aktualisieren
          </DropdownItem>
          <DropdownItem
            onSelect={() => {
              close();
              void onAiPreview(stock.isin);
            }}
          >
            KI-Vorschlag anzeigen
          </DropdownItem>
          <DropdownItem
            onSelect={() => {
              close();
              void onEvaluate(stock.isin);
            }}
          >
            KI-Empfehlung übernehmen
          </DropdownItem>
          <DropdownItem
            onSelect={() => {
              close();
              void onToggleLock(stock.isin, "recommendation", !recLocked);
            }}
          >
            {recLocked ? "Empfehlung entsperren" : "Empfehlung sperren"}
          </DropdownItem>
          <DropdownItem
            onSelect={() => {
              close();
              onEdit(stock);
            }}
          >
            Bearbeiten
          </DropdownItem>
          <DropdownSeparator />
          <DropdownItem
            danger
            onSelect={() => {
              close();
              void onDelete(stock);
            }}
          >
            Löschen
          </DropdownItem>
        </>
      )}
    </Dropdown>
  );
}
