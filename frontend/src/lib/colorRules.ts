import { Stock } from "../types";

export interface ColorThresholds {
  strongGainPct: number;
  strongLossPct: number;
  highDividendPct: number;
  targetDistancePct: number;
  strongFundamentalScore: number;
  weakFundamentalScore: number;
}

export const defaultThresholds: ColorThresholds = {
  strongGainPct: 4,
  strongLossPct: -4,
  highDividendPct: 4,
  targetDistancePct: 10,
  strongFundamentalScore: 8,
  weakFundamentalScore: 3,
};

export function rowClass(stock: Stock): string {
  if (stock.recommendation === "buy") return "row-buy";
  if (stock.recommendation === "risk_buy") return "row-risk";
  return "";
}

export function changeClass(value: number | null, thresholds: ColorThresholds = defaultThresholds): string {
  if (value === null) return "";
  if (value > thresholds.strongGainPct) return "pill-green";
  if (value < thresholds.strongLossPct) return "pill-red";
  return "";
}

export function valuationClass(value: number | null): string {
  if (value === null) return "";
  if (value < 0) return "pill-blue";
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

export function scoreClass(value: number | null, thresholds: ColorThresholds = defaultThresholds): string {
  if (value === null) return "";
  if (value >= thresholds.strongFundamentalScore) return "pill-green";
  if (value <= thresholds.weakFundamentalScore) return "pill-red";
  return "";
}
