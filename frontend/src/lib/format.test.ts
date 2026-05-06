import { describe, expect, it } from "vitest";

import { formatDateOnly, parseBackendDate } from "./format";

describe("parseBackendDate", () => {
  it("treats naive ISO strings as UTC (backend ships naive UTC datetimes)", () => {
    // 2026-05-03T14:29:00Z → Unix ms 1778250540000.
    expect(parseBackendDate("2026-05-03T14:29:00").getTime()).toBe(
      Date.UTC(2026, 4, 3, 14, 29, 0)
    );
  });

  it("preserves an explicit Z suffix", () => {
    expect(parseBackendDate("2026-05-03T14:29:00Z").getTime()).toBe(
      Date.UTC(2026, 4, 3, 14, 29, 0)
    );
  });

  it("preserves explicit offsets", () => {
    expect(parseBackendDate("2026-05-03T16:29:00+02:00").getTime()).toBe(
      Date.UTC(2026, 4, 3, 14, 29, 0)
    );
    expect(parseBackendDate("2026-05-03T09:29:00-05:00").getTime()).toBe(
      Date.UTC(2026, 4, 3, 14, 29, 0)
    );
  });

  it("keeps fractional seconds intact", () => {
    expect(parseBackendDate("2026-05-03T14:29:00.123").getTime()).toBe(
      Date.UTC(2026, 4, 3, 14, 29, 0) + 123
    );
  });

  it("does not touch date-only strings (already UTC midnight per ECMA)", () => {
    expect(parseBackendDate("2026-05-03").getTime()).toBe(
      Date.UTC(2026, 4, 3, 0, 0, 0)
    );
  });
});

describe("formatDateOnly", () => {
  it("renders date-only backend values without a timezone-derived clock", () => {
    const rendered = formatDateOnly("2026-05-03");
    expect(rendered).toMatch(/03\.05\.2026|3\.5\.2026/);
    expect(rendered).not.toContain(":");
  });
});
