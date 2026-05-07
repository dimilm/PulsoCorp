/** Breakpoint thresholds — must stay in sync with --bp-* tokens in tokens.css */
export const BP_SM = 480;
export const BP_MD = 768;
export const BP_LG = 1080;

export type Breakpoint = "mobile" | "tablet" | "desktop";

export function getBreakpoint(width: number): Breakpoint {
  if (width <= BP_MD) return "mobile";
  if (width <= BP_LG) return "tablet";
  return "desktop";
}
