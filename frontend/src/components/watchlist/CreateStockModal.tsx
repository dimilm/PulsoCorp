import { FormEvent, useEffect, useState } from "react";
import { api } from "../../api/client";
import { CreateStockForm, StockFormErrors, StockFormValues } from "../CreateStockForm";
import { Modal } from "../Modal";
import { extractApiError } from "../../lib/apiError";
import { toast } from "../../lib/toast";
import { validateCreateStock } from "../../lib/stockValidation";
import { useSectorSuggestions } from "../../hooks/useStockQueries";

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
  /** Optional pre-fill values. When provided, ISIN and name are seeded into
   *  the form on open. Both fields remain editable so the user can correct them. */
  initialValues?: { isin?: string; name?: string };
}

export function CreateStockModal({ open, onClose, tagSuggestions, onCreated, initialValues }: Props) {
  const [newStock, setNewStock] = useState<StockFormValues>(EMPTY_STOCK);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createFieldErrors, setCreateFieldErrors] = useState<StockFormErrors>({});
  const [isPending, setIsPending] = useState(false);

  const { data: sectorSuggestions } = useSectorSuggestions();

  // Re-initialise form state whenever the modal opens, seeding from initialValues
  // when provided (e.g. opened from the Jobs page with a pre-filled ISIN/name).
  useEffect(() => {
    if (open) {
      setNewStock(
        initialValues
          ? { ...EMPTY_STOCK, isin: initialValues.isin ?? "", name: initialValues.name ?? "" }
          : EMPTY_STOCK
      );
      setCreateError(null);
      setCreateFieldErrors({});
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

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
    setIsPending(true);
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
      toast.success("Unternehmen zur Watchlist hinzugefügt.");
      await onCreated();
    } catch (error) {
      setCreateError(extractApiError(error, "Unternehmen konnte nicht angelegt werden."));
    } finally {
      setIsPending(false);
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
            disabled={!isCreateValid || isPending}
          >
            {isPending ? "Speichern…" : "Speichern"}
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
        sectorSuggestions={sectorSuggestions ?? []}
        isPending={isPending}
      />
      {createError && (
        <p className="form-banner-error" role="alert">
          {createError}
        </p>
      )}
    </Modal>
  );
}
