export interface ColorThresholds {
  strongGainPct: number;
  strongLossPct: number;
  highDividendPct: number;
  targetDistancePct: number;
}

export const defaultThresholds: ColorThresholds = {
  strongGainPct: 4,
  strongLossPct: -4,
  highDividendPct: 4,
  targetDistancePct: 10,
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
