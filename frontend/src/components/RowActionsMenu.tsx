import { Stock } from "../types";
import { Dropdown, DropdownItem, DropdownSeparator } from "./Dropdown";
import { KebabIcon } from "./icons";

interface Props {
  stock: Stock;
  onRefresh: (isin: string) => Promise<void>;
  onEdit: (stock: Stock) => void;
  onDelete: (stock: Stock) => Promise<void>;
  refreshDisabled?: boolean;
}

export default function RowActionsMenu({
  stock,
  onRefresh,
  onEdit,
  onDelete,
  refreshDisabled = false,
}: Props) {
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
            disabled={refreshDisabled}
            onSelect={() => {
              close();
              void onRefresh(stock.isin);
            }}
          >
            {refreshDisabled ? "Aktualisierung läuft…" : "Aktualisieren"}
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
