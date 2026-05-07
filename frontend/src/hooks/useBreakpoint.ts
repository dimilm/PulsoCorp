import { useEffect, useState } from "react";

import { type Breakpoint, BP_LG, BP_MD, getBreakpoint } from "../lib/breakpoints";

/** Returns the current layout breakpoint, updated reactively on resize.
 *  Defaults to "desktop" on the first render (SSR-safe). */
export function useBreakpoint(): Breakpoint {
  const [bp, setBp] = useState<Breakpoint>(() =>
    typeof window === "undefined" ? "desktop" : getBreakpoint(window.innerWidth)
  );

  useEffect(() => {
    const mqlMd = window.matchMedia(`(max-width: ${BP_MD}px)`);
    const mqlLg = window.matchMedia(`(max-width: ${BP_LG}px)`);

    function update() {
      setBp(getBreakpoint(window.innerWidth));
    }

    mqlMd.addEventListener("change", update);
    mqlLg.addEventListener("change", update);
    update();

    return () => {
      mqlMd.removeEventListener("change", update);
      mqlLg.removeEventListener("change", update);
    };
  }, []);

  return bp;
}

/** Shortcut: returns true when the viewport is ≤ 768px (mobile). */
export function useIsMobile(): boolean {
  return useBreakpoint() === "mobile";
}
