// Centralised formatters with German locale. Replaces the per-page copies that
// existed in StockDetailPage / RunsPage / AgentCard / ScenarioResultView.

const LOCALE = "de-DE";
const DASH = "–";

function isMissing(value: unknown): boolean {
  return value === null || value === undefined || (typeof value === "number" && Number.isNaN(value));
}

// Backend ships *naive* UTC ISO strings ("2026-05-03T14:29:00") because the
// SQLAlchemy `DateTime` columns store naive datetimes via `app.core.time.utcnow`.
// Without a timezone designator the browser interprets such strings as *local*
// time, which silently shifts every timestamp by the host's UTC offset (e.g.
// +2h in CEST → "Bisher" counter starts at 2h instead of 0). Force UTC parsing
// by appending `Z` when the string carries time-of-day but no tz info. Inputs
// that already include a tz (`Z`, `+02:00`, `-0500`) or are date-only pass
// through unchanged.
export function parseBackendDate(value: string): Date {
  const hasTime = /T\d{2}:\d{2}/.test(value);
  const hasTz = /[zZ]$|[+-]\d{2}:?\d{2}$/.test(value);
  return new Date(hasTime && !hasTz ? `${value}Z` : value);
}

export function formatNumber(value: number | null | undefined, fractionDigits = 2): string {
  if (isMissing(value)) return DASH;
  return (value as number).toLocaleString(LOCALE, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}

// Renders a percent value. By default the unit (` %`) is appended (Schule A:
// "+1.42 %"). For Schule-B style tables that show `(%)` in the column header
// instead of in every cell, pass `withUnit: false` to drop the suffix while
// keeping the explicit sign for signed values.
export function formatPercent(
  value: number | null | undefined,
  fractionDigits = 2,
  options: { showSign?: boolean; withUnit?: boolean } = {}
): string {
  if (isMissing(value)) return DASH;
  const { showSign = true, withUnit = true } = options;
  const v = value as number;
  const sign = showSign && v > 0 ? "+" : "";
  const unit = withUnit ? " %" : "";
  return `${sign}${v.toFixed(fractionDigits)}${unit}`;
}

export function formatCurrency(
  value: number | null | undefined,
  currency: string | null | undefined
): string {
  if (isMissing(value)) return DASH;
  const code = currency || "EUR";
  const v = value as number;
  try {
    return v.toLocaleString(LOCALE, {
      style: "currency",
      currency: code,
      maximumFractionDigits: 2,
    });
  } catch {
    return `${v.toFixed(2)} ${code}`;
  }
}

// "Large" currency formatting: collapses millions / billions / trillions to
// short suffixes so the value fits in a KPI tile.
export function formatLargeCurrency(
  value: number | null | undefined,
  currency: string | null | undefined
): string {
  if (isMissing(value)) return DASH;
  const v = value as number;
  const code = currency || "EUR";
  const abs = Math.abs(v);
  let scaled: number;
  let suffix: string;
  if (abs >= 1e12) {
    scaled = v / 1e12;
    suffix = "Bio.";
  } else if (abs >= 1e9) {
    scaled = v / 1e9;
    suffix = "Mrd.";
  } else if (abs >= 1e6) {
    scaled = v / 1e6;
    suffix = "Mio.";
  } else {
    return formatCurrency(v, code);
  }
  return `${scaled.toLocaleString(LOCALE, { maximumFractionDigits: 2 })} ${suffix} ${code}`;
}

// Long form date+time: "26.04.26, 13:42"
export function formatDate(value: string | null | undefined): string {
  if (!value) return DASH;
  const d = parseBackendDate(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString(LOCALE, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// Date-only ("26.04.2026"). Important for backend `date` fields like
// `latest_snapshot_date` where no time-of-day exists.
export function formatDateOnly(value: string | null | undefined): string {
  if (!value) return DASH;
  const d = parseBackendDate(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString(LOCALE, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

// Run history-style timestamp ("26.04.26, 13:42:07")
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return DASH;
  const d = parseBackendDate(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString(LOCALE, { dateStyle: "short", timeStyle: "medium" });
}

// Time-only ("13:42:07")
export function formatTimeShort(value: string | null | undefined): string {
  if (!value) return DASH;
  const d = parseBackendDate(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleTimeString(LOCALE, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

// Compact duration: "—" for missing, "0s" / "42s" / "3m 7s" / "12m" otherwise.
// Pass `dashOnZero=false` for live counters that should always render a number,
// even at start (0s).
export function formatDuration(
  seconds: number | null | undefined,
  options: { dashOnZero?: boolean } = {}
): string {
  const { dashOnZero = true } = options;
  if (seconds == null) return DASH;
  if (seconds <= 0) return dashOnZero ? DASH : "0s";
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s ? `${m}m ${s}s` : `${m}m`;
}
