import {
  chain,
  currencyCode,
  exactLength,
  isin,
  nonNegativeInt,
  optional,
  pattern,
  required,
  type Schema,
  url,
} from "./validation";

/** All values come from `<input>` / `<select>` / `<textarea>` so they are
 *  always strings (even numeric fields). The schemas reflect that – the
 *  caller is responsible for parsing strings into ints/numbers AFTER
 *  validation has passed. */
export interface CreateStockFormShape {
  isin: string;
  name: string;
  currency: string;
  tranches: string;
}

export const createStockSchema: Schema<CreateStockFormShape> = {
  isin: chain(
    required("ISIN ist ein Pflichtfeld."),
    exactLength(12, "ISIN muss genau 12 Zeichen lang sein."),
    isin("Nur Buchstaben und Ziffern erlaubt.")
  ),
  name: required("Name ist ein Pflichtfeld."),
  // Currency is intentionally not validated on create – the modal's UI keeps
  // it bounded to a `<select>` of known codes plus a free-form 3-char fallback
  // and previous behaviour accepted whatever the user typed.
  tranches: optional(nonNegativeInt()),
};

export interface EditStockFormShape {
  name: string;
  currency: string;
  tranches: string;
  ticker_override: string;
  link_yahoo: string;
  link_finanzen: string;
  link_onvista_chart: string;
  link_onvista_fundamental: string;
}

const optionalUrl = optional(url());

export const editStockSchema: Schema<EditStockFormShape> = {
  name: required("Name ist ein Pflichtfeld."),
  currency: optional(currencyCode()),
  tranches: optional(nonNegativeInt("Tranchen müssen eine ganze Zahl ≥ 0 sein.")),
  // Ticker override is uppercase letters/digits/dot/dash (e.g. "SIE.DE",
  // "BRK-B"). The form already strips whitespace and uppercases on input,
  // so this just guards against pasted garbage like "  SIE DE ".
  ticker_override: optional(
    pattern(/^[A-Z0-9][A-Z0-9.-]*$/, "Ticker: Buchstaben, Ziffern, Punkt oder Bindestrich.")
  ),
  link_yahoo: optionalUrl,
  link_finanzen: optionalUrl,
  link_onvista_chart: optionalUrl,
  link_onvista_fundamental: optionalUrl,
};
