import "@testing-library/jest-dom/vitest";

// jsdom does not implement window.matchMedia. Provide a stub that returns a
// non-matching MediaQueryList so components depending on useBreakpoint default
// to "desktop" in tests (matching the SSR-safe fallback).
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string): MediaQueryList => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});
