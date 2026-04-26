/* Tiny, dependency-free validation combinator layer.
 *
 * Design goals:
 *   - Validators are plain pure functions: `(value) => string | null`. A `null`
 *     result means "valid", anything else is the localized error message.
 *   - Composability: `chain(a, b, c)` returns the first error, short-circuiting
 *     so each validator can assume earlier ones have already passed.
 *   - Schemas are objects keyed by field name. `validateSchema(values, schema)`
 *     produces `Partial<Record<keyof T, string>>` errors that drop straight
 *     into the existing `*-form` UI markup (`.field.has-error`/`.field-error`).
 *
 * Why no zod / yup? The forms are small (~3 forms, <15 fields total). Pulling
 * in a runtime schema lib for that would add dependency surface for very
 * little gain. The combinators below cover what we need (presence, length,
 * regex, integer range, optional URL, ISIN-format) and are trivially testable.
 */

export type Validator<T> = (value: T) => string | null;

export type Schema<T> = { [K in keyof T]?: Validator<T[K]> };

export type Errors<T> = Partial<Record<keyof T, string>>;

/** Runs every field validator in `schema` against the matching value in
 *  `values` and returns an object with the first error per field. Fields
 *  without a validator are skipped, fields with no error are absent from the
 *  result so callers can `Object.keys(errors).length === 0` for a quick
 *  "is the form valid" check. */
export function validateSchema<T>(values: T, schema: Schema<T>): Errors<T> {
  const out: Errors<T> = {};
  for (const key of Object.keys(schema) as (keyof T)[]) {
    const validate = schema[key];
    if (!validate) continue;
    const message = validate(values[key]);
    if (message) out[key] = message;
  }
  return out;
}

/** Combine validators left-to-right. The first non-null result short-circuits;
 *  this lets later validators assume earlier preconditions (e.g. "non-empty",
 *  "numeric") have already passed. */
export function chain<T>(...validators: Validator<T>[]): Validator<T> {
  return (value) => {
    for (const v of validators) {
      const result = v(value);
      if (result) return result;
    }
    return null;
  };
}

/** Wraps a validator so empty / whitespace-only strings always pass. Useful
 *  for optional fields where business rules only apply when a value is
 *  actually entered (URLs, custom currency, tranches, etc.). */
export function optional(validator: Validator<string>): Validator<string> {
  return (value) => (value.trim() === "" ? null : validator(value));
}

export function required(message = "Pflichtfeld."): Validator<string> {
  return (value) => (value.trim().length === 0 ? message : null);
}

export function exactLength(length: number, message?: string): Validator<string> {
  return (value) =>
    value.length === length
      ? null
      : message ?? `Genau ${length} Zeichen erforderlich.`;
}

export function maxLength(length: number, message?: string): Validator<string> {
  return (value) =>
    value.length <= length
      ? null
      : message ?? `Maximal ${length} Zeichen erlaubt.`;
}

export function pattern(re: RegExp, message: string): Validator<string> {
  return (value) => (re.test(value) ? null : message);
}

/** ISO-6166 ISIN format: 2 letters (country) + 9 alphanumeric + 1 check digit.
 *  We do NOT verify the Luhn checksum here on purpose – the backend does
 *  that, and a typed-but-not-yet-finished value should not block early
 *  feedback on obviously bad inputs. */
export function isin(message = "ISIN: 12 Zeichen, nur Buchstaben & Ziffern."): Validator<string> {
  return (value) => {
    const trimmed = value.trim().toUpperCase();
    if (trimmed.length !== 12) return message;
    if (!/^[A-Z0-9]{12}$/.test(trimmed)) return message;
    return null;
  };
}

/** Currency code: 3 uppercase letters (ISO-4217 shape, not membership). */
export function currencyCode(
  message = "Währungs-Code: 3 Buchstaben (z. B. EUR)."
): Validator<string> {
  return (value) => (/^[A-Z]{3}$/.test(value.trim().toUpperCase()) ? null : message);
}

/** Non-negative integer parsed from a free-form string. Empty strings fail –
 *  wrap with `optional()` if blank should be accepted as "not specified". */
export function nonNegativeInt(
  message = "Bitte eine ganze Zahl ≥ 0 angeben."
): Validator<string> {
  return (value) => {
    const trimmed = value.trim();
    if (trimmed === "") return message;
    const n = Number(trimmed);
    if (!Number.isFinite(n) || !Number.isInteger(n) || n < 0) return message;
    return null;
  };
}

/** Loose URL check that accepts http/https only and rejects spaces. We use
 *  the WHATWG URL parser so locale-specific edge cases (IDN hosts etc.) just
 *  work. Empty values fail – wrap with `optional()` for optional-URL fields. */
export function url(
  message = "Bitte eine gültige http(s)-URL angeben."
): Validator<string> {
  return (value) => {
    const trimmed = value.trim();
    if (trimmed === "") return message;
    if (/\s/.test(trimmed)) return message;
    try {
      const parsed = new URL(trimmed);
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return message;
      return null;
    } catch {
      return message;
    }
  };
}

export function oneOf<T extends string>(
  allowed: readonly T[],
  message?: string
): Validator<T | string> {
  return (value) =>
    (allowed as readonly string[]).includes(value)
      ? null
      : message ?? `Erlaubt: ${allowed.join(", ")}.`;
}
