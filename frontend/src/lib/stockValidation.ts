import type { StockFormErrors, StockFormValues } from "../components/CreateStockForm";
import { createStockSchema } from "./stockFormSchemas";
import { validateSchema } from "./validation";

/** Thin wrapper around `validateSchema(createStockSchema)` so the watchlist
 *  page keeps its existing call site (`validateCreateStock(values)`). The
 *  schema validates the few fields that have rules; non-validated fields
 *  (sector, burggraben, tags) are passed through untouched. */
export function validateCreateStock(values: StockFormValues): StockFormErrors {
  return validateSchema(values, createStockSchema) as StockFormErrors;
}
