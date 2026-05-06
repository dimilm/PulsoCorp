import { FormEvent, useState } from "react";
import { api } from "../../api/client";
import { CreateStockForm, StockFormErrors, StockFormValues } from "../CreateStockForm";
import { Modal } from "../Modal";
import { extractApiError } from "../../lib/apiError";
import { validateCreateStock } from "../../lib/stockValidation";

const EMPTY_STOCK: StockFormValues = {
  isin: "",
  name: "",
  sector: "",
  currency: "EUR",
  tranches: "",
  tags: [],
};

interface Props {
  open: boolean;
  onClose: () => void;
  tagSuggestions: { name: string; count: number }[];
  onCreated: () => Promise<void>;
}

export function CreateStockModal({ open, onClose, tagSuggestions, onCreated }: Props) {
  const [newStock, setNewStock] = useState<StockFormValues>(EMPTY_STOCK);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createFieldErrors, setCreateFieldErrors] = useState<StockFormErrors>({});

  const isCreateValid =
    newStock.isin.trim().length === 12 &&
    /^[A-Z0-9]{12}$/.test(newStock.isin.trim().toUpperCase()) &&
    newStock.name.trim().length > 0;

  function handleClose() {
    setNewStock(EMPTY_STOCK);
    setCreateError(null);
    setCreateFieldErrors({});
    onClose();
  }

  async function createStock(e: FormEvent) {
    e.preventDefault();
    setCreateError(null);
    const errs = validateCreateStock(newStock);
    setCreateFieldErrors(errs);
    if (Object.keys(errs).length > 0) return;
    try {
      await api.post("/stocks", {
        isin: newStock.isin.trim().toUpperCase(),
        name: newStock.name.trim(),
        sector: newStock.sector.trim() || null,
        currency: newStock.currency.trim().toUpperCase() || null,
        tranches: Math.max(0, Number(newStock.tranches) || 0),
        tags: newStock.tags,
      });
      handleClose();
      await onCreated();
    } catch (error) {
      setCreateError(extractApiError(error, "Unternehmen konnte nicht angelegt werden."));
    }
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Unternehmen hinzufügen"
      subtitle="Trage die Stammdaten manuell ein. Marktdaten werden anschließend automatisch ergänzt."
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={handleClose}>
            Abbrechen
          </button>
          <button
            type="submit"
            form="create-stock-form"
            className="btn-primary"
            disabled={!isCreateValid}
          >
            Speichern
          </button>
        </>
      }
    >
      <CreateStockForm
        formId="create-stock-form"
        values={newStock}
        onChange={setNewStock}
        onSubmit={createStock}
        errors={createFieldErrors}
        tagSuggestions={tagSuggestions}
      />
      {createError && (
        <p className="form-banner-error" role="alert">
          {createError}
        </p>
      )}
    </Modal>
  );
}
