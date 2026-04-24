import { describe, expect, it } from "vitest";

import {
  changeClass,
  defaultThresholds,
  dividendClass,
  rowClass,
  scoreClass,
  targetClass,
  valuationClass,
} from "./colorRules";
import type { Stock } from "../types";

function stock(partial: Omit<Partial<Stock>, "recommendation"> & { recommendation?: string }): Stock {
  return {
    isin: "US0000000000",
    name: "Test",
    sector: "Tech",
    currency: "USD",
    burggraben: false,
    tranches: 0,
    tags: [],
    recommendation: "none",
    ...partial,
  } as unknown as Stock;
}

describe("rowClass", () => {
  it("highlights a buy recommendation", () => {
    expect(rowClass(stock({ recommendation: "buy" }))).toBe("row-buy");
  });
  it("highlights a risk_buy recommendation", () => {
    expect(rowClass(stock({ recommendation: "risk_buy" }))).toBe("row-risk");
  });
  it("returns empty for other recommendations", () => {
    expect(rowClass(stock({ recommendation: "hold" }))).toBe("");
    expect(rowClass(stock({ recommendation: "none" }))).toBe("");
  });
});

describe("changeClass", () => {
  it("returns empty for null", () => {
    expect(changeClass(null)).toBe("");
  });
  it("flags strong gains", () => {
    expect(changeClass(defaultThresholds.strongGainPct + 1)).toBe("pill-green");
  });
  it("flags strong losses", () => {
    expect(changeClass(defaultThresholds.strongLossPct - 1)).toBe("pill-red");
  });
  it("returns empty inside the neutral band", () => {
    expect(changeClass(0)).toBe("");
    expect(changeClass(defaultThresholds.strongGainPct)).toBe("");
  });
});

describe("valuationClass", () => {
  it("highlights negative discounts as undervalued", () => {
    expect(valuationClass(-5)).toBe("pill-blue");
  });
  it("ignores positive discounts", () => {
    expect(valuationClass(5)).toBe("");
  });
  it("handles null", () => {
    expect(valuationClass(null)).toBe("");
  });
});

describe("targetClass", () => {
  it("flags large positive distance to target", () => {
    expect(targetClass(defaultThresholds.targetDistancePct + 1)).toBe("pill-cyan");
  });
  it("ignores values below the threshold", () => {
    expect(targetClass(defaultThresholds.targetDistancePct)).toBe("");
  });
});

describe("dividendClass", () => {
  it("flags high dividends", () => {
    expect(dividendClass(defaultThresholds.highDividendPct + 0.1)).toBe("pill-cyan");
  });
});

describe("scoreClass", () => {
  it("flags strong fundamental scores", () => {
    expect(scoreClass(defaultThresholds.strongFundamentalScore)).toBe("pill-green");
  });
  it("flags weak fundamental scores", () => {
    expect(scoreClass(defaultThresholds.weakFundamentalScore)).toBe("pill-red");
  });
  it("returns empty between the bands", () => {
    expect(scoreClass(5)).toBe("");
  });
});
