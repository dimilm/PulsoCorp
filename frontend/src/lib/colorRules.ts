export interface ColorThresholds {
  strongGainPct: number;
  strongLossPct: number;
  highDividendPct: number;
  targetDistancePct: number;
  // Equity-ratio traffic light (in percent):
  //   value < equityRatioMinPct       → bad (red)
  //   equityRatioMinPct ≤ value ≤ Good → warn (yellow)
  //   value > equityRatioGoodPct      → good (green)
  equityRatioMinPct: number;
  equityRatioGoodPct: number;
}

export const defaultThresholds: ColorThresholds = {
  strongGainPct: 4,
  strongLossPct: -4,
  highDividendPct: 4,
  targetDistancePct: 10,
  equityRatioMinPct: 30,
  equityRatioGoodPct: 35,
};

export function changeClass(value: number | null, thresholds: ColorThresholds = defaultThresholds): string {
  if (value === null) return "";
  if (value > thresholds.strongGainPct) return "pill-green";
  if (value < thresholds.strongLossPct) return "pill-red";
  return "";
}

export function targetClass(value: number | null, thresholds: ColorThresholds = defaultThresholds): string {
  if (value === null) return "";
  if (value > thresholds.targetDistancePct) return "pill-cyan";
  return "";
}

export function dividendClass(value: number | null, thresholds: ColorThresholds = defaultThresholds): string {
  if (value === null) return "";
  if (value > thresholds.highDividendPct) return "pill-cyan";
  return "";
}

// Equity-ratio traffic light. Returns one of "kpi-bad" / "kpi-warn" / "kpi-good"
// (or "" when the value is missing) so callers can apply it to whatever
// container makes sense — currently the StockDetail KPI tile.
export function equityRatioClass(
  value: number | null,
  thresholds: ColorThresholds = defaultThresholds
): string {
  if (value === null) return "";
  if (value < thresholds.equityRatioMinPct) return "kpi-bad";
  if (value <= thresholds.equityRatioGoodPct) return "kpi-warn";
  return "kpi-good";
}
