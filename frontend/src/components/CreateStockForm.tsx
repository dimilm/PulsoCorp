import { FormEvent, useMemo } from "react";
import { TagInput } from "./TagInput";
import { SectorSuggestion } from "../hooks/useStockQueries";
import { SectorAutocomplete } from "./SectorAutocomplete";

export interface StockFormValues {
  isin: string;
  name: string;
  sector: string;
  currency: string;
  tranches: string;
  tags: string[];
}

export type StockFormErrors = Partial<Record<keyof StockFormValues, string>>;

interface CreateStockFormProps {
  formId: string;
  values: StockFormValues;
  onChange: (next: StockFormValues) => void;
  onSubmit: (e: FormEvent) => void;
  errors?: StockFormErrors;
  tagSuggestions?: { name: string; count?: number }[];
  sectorSuggestions?: SectorSuggestion[];
  isPending?: boolean;
}

const KNOWN_CURRENCIES = ["EUR", "USD", "CHF", "GBP", "JPY"] as const;

// Form for the "Unternehmen hinzufügen" modal on the watchlist. Editing
// existing stocks is handled by the dedicated StockEditPage – this component
// always renders the ISIN field and is intentionally not reusable for edit.
export function CreateStockForm({
  formId,
  values,
  onChange,
  onSubmit,
  errors = {},
  tagSuggestions = [],
  sectorSuggestions,
  isPending,
}: CreateStockFormProps) {
  const set = <K extends keyof StockFormValues>(key: K, v: StockFormValues[K]) =>
    onChange({ ...values, [key]: v });

  const isCustomCurrency = useMemo(
    () =>
      values.currency !== "" &&
      !(KNOWN_CURRENCIES as readonly string[]).includes(values.currency),
    [values.currency]
  );
  const currencySelectValue = isCustomCurrency ? "__other__" : values.currency || "EUR";
  const isinRemaining = Math.max(0, 12 - values.isin.length);

  return (
    <form id={formId} className="stock-form" onSubmit={onSubmit} noValidate>
      <fieldset className="form-section">
        <legend>Stammdaten</legend>

        <div className={`field ${errors.isin ? "has-error" : ""}`}>
          <label htmlFor={`${formId}-isin`}>
            ISIN <span className="required" aria-hidden="true">*</span>
          </label>
          <input
            id={`${formId}-isin`}
            value={values.isin}
            onChange={(e) => set("isin", e.target.value.toUpperCase().replace(/\s+/g, ""))}
            placeholder="z. B. DE0007164600"
            maxLength={12}
            autoComplete="off"
            spellCheck={false}
            required
          />
          <div className="field-meta">
            <span className="helper">12 Zeichen, Buchstaben & Ziffern</span>
            {values.isin.length > 0 && isinRemaining > 0 && (
              <span className="helper helper-soft">noch {isinRemaining}</span>
            )}
          </div>
          {errors.isin && <div className="field-error">{errors.isin}</div>}
        </div>

        <div className={`field ${errors.name ? "has-error" : ""}`}>
          <label htmlFor={`${formId}-name`}>
            Name <span className="required" aria-hidden="true">*</span>
          </label>
          <input
            id={`${formId}-name`}
            value={values.name}
            onChange={(e) => set("name", e.target.value)}
            placeholder="z. B. Siemens AG"
            required
          />
          {errors.name && <div className="field-error">{errors.name}</div>}
        </div>
      </fieldset>

      <fieldset className="form-section">
        <legend>Klassifizierung</legend>

        <div className="field">
          <label htmlFor={`${formId}-sector`}>Sektor</label>
          <SectorAutocomplete
            id={`${formId}-sector`}
            value={values.sector}
            onChange={(v) => set("sector", v)}
            suggestions={sectorSuggestions}
            disabled={isPending}
            placeholder="z. B. Industrie, Tech, Healthcare"
          />
        </div>
      </fieldset>

      <fieldset className="form-section">
        <legend>Tags</legend>
        <div className="field">
          <label htmlFor={`${formId}-tags`}>Tags</label>
          <TagInput
            id={`${formId}-tags`}
            value={values.tags}
            onChange={(next) => set("tags", next)}
            suggestions={tagSuggestions}
            placeholder="Tag hinzufügen…"
          />
          <span className="helper">Mit Enter oder Komma trennen. Vorschläge per Pfeiltasten wählen.</span>
        </div>
      </fieldset>

      <fieldset className="form-section">
        <legend>Position</legend>

        <div className="field-row">
          <div className="field">
            <label htmlFor={`${formId}-currency`}>Währung</label>
            <select
              id={`${formId}-currency`}
              value={currencySelectValue}
              onChange={(e) => {
                const v = e.target.value;
                if (v === "__other__") {
                  set("currency", isCustomCurrency ? values.currency : "");
                } else {
                  set("currency", v);
                }
              }}
            >
              {KNOWN_CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
              <option value="__other__">Andere…</option>
            </select>
            {currencySelectValue === "__other__" && (
              <input
                className="field-extra"
                value={values.currency}
                onChange={(e) => set("currency", e.target.value.toUpperCase().slice(0, 3))}
                placeholder="ISO-Code (3 Zeichen)"
                maxLength={3}
              />
            )}
          </div>

          <div className={`field ${errors.tranches ? "has-error" : ""}`}>
            <label htmlFor={`${formId}-tranches`}>Tranchen</label>
            <input
              id={`${formId}-tranches`}
              type="number"
              min={0}
              inputMode="numeric"
              value={values.tranches}
              onChange={(e) => set("tranches", e.target.value)}
              placeholder="0"
            />
            <span className="helper">Anzahl gekaufter Positionen</span>
            {errors.tranches && <div className="field-error">{errors.tranches}</div>}
          </div>
        </div>
      </fieldset>
    </form>
  );
}

export default CreateStockForm;
