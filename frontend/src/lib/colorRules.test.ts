import { describe, expect, it } from "vitest";

import {
  changeClass,
  defaultThresholds,
  dividendClass,
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
