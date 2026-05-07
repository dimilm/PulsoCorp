import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useBreakpoint, useIsMobile } from "./useBreakpoint";

type MqlListener = (e: MediaQueryListEvent) => void;

function makeMql(matches: boolean) {
  const listeners: MqlListener[] = [];
  return {
    matches,
    addEventListener: vi.fn((_: string, cb: MqlListener) => listeners.push(cb)),
    removeEventListener: vi.fn((_: string, cb: MqlListener) => {
      const idx = listeners.indexOf(cb);
      if (idx !== -1) listeners.splice(idx, 1);
    }),
    _fire(newMatches: boolean) {
      listeners.forEach((cb) => cb({ matches: newMatches } as MediaQueryListEvent));
    },
  };
}

describe("useBreakpoint", () => {
  let originalInnerWidth: PropertyDescriptor | undefined;
  let mqlMd: ReturnType<typeof makeMql>;
  let mqlLg: ReturnType<typeof makeMql>;

  beforeEach(() => {
    originalInnerWidth = Object.getOwnPropertyDescriptor(window, "innerWidth");

    mqlMd = makeMql(false);
    mqlLg = makeMql(false);

    vi.spyOn(window, "matchMedia").mockImplementation((query: string) => {
      if (query.includes("768")) return mqlMd as unknown as MediaQueryList;
      if (query.includes("1080")) return mqlLg as unknown as MediaQueryList;
      return makeMql(false) as unknown as MediaQueryList;
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    if (originalInnerWidth) {
      Object.defineProperty(window, "innerWidth", originalInnerWidth);
    }
  });

  function setWidth(width: number) {
    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: width,
    });
  }

  it("returns 'mobile' when innerWidth <= 768", () => {
    setWidth(375);
    const { result } = renderHook(() => useBreakpoint());
    expect(result.current).toBe("mobile");
  });

  it("returns 'tablet' when innerWidth is 900", () => {
    setWidth(900);
    const { result } = renderHook(() => useBreakpoint());
    expect(result.current).toBe("tablet");
  });

  it("returns 'desktop' when innerWidth > 1080", () => {
    setWidth(1440);
    const { result } = renderHook(() => useBreakpoint());
    expect(result.current).toBe("desktop");
  });

  it("updates when matchMedia fires a change event", () => {
    setWidth(1440);
    const { result } = renderHook(() => useBreakpoint());
    expect(result.current).toBe("desktop");

    // Simulate resize to mobile
    act(() => {
      setWidth(375);
      mqlMd._fire(true);
    });

    expect(result.current).toBe("mobile");
  });
});

describe("useIsMobile", () => {
  afterEach(() => vi.restoreAllMocks());

  it("returns true on mobile width", () => {
    Object.defineProperty(window, "innerWidth", { writable: true, configurable: true, value: 375 });
    vi.spyOn(window, "matchMedia").mockImplementation(() => makeMql(true) as unknown as MediaQueryList);
    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(true);
  });

  it("returns false on desktop width", () => {
    Object.defineProperty(window, "innerWidth", { writable: true, configurable: true, value: 1440 });
    vi.spyOn(window, "matchMedia").mockImplementation(() => makeMql(false) as unknown as MediaQueryList);
    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(false);
  });
});
