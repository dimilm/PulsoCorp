import { describe, expect, it } from "vitest";

import {
  changeClass,
  defaultThresholds,
  dividendClass,
  equityRatioClass,
  targetClass,
} from "./colorRules";

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

describe("equityRatioClass", () => {
  it("returns empty for null", () => {
    expect(equityRatioClass(null)).toBe("");
  });
  it("flags weak equity ratios as bad", () => {
    expect(equityRatioClass(defaultThresholds.equityRatioMinPct - 0.1)).toBe("kpi-bad");
    expect(equityRatioClass(0)).toBe("kpi-bad");
  });
  it("treats the warn band as yellow (inclusive on both ends)", () => {
    expect(equityRatioClass(defaultThresholds.equityRatioMinPct)).toBe("kpi-warn");
    expect(equityRatioClass(defaultThresholds.equityRatioGoodPct)).toBe("kpi-warn");
    const mid = (defaultThresholds.equityRatioMinPct + defaultThresholds.equityRatioGoodPct) / 2;
    expect(equityRatioClass(mid)).toBe("kpi-warn");
  });
  it("flags strong equity ratios as good", () => {
    expect(equityRatioClass(defaultThresholds.equityRatioGoodPct + 0.1)).toBe("kpi-good");
    expect(equityRatioClass(80)).toBe("kpi-good");
  });
});
