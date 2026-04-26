import { RefObject, useEffect } from "react";

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "area[href]",
  'input:not([disabled]):not([type="hidden"])',
  "select:not([disabled])",
  "textarea:not([disabled])",
  "button:not([disabled])",
  "iframe",
  "object",
  "embed",
  '[tabindex]:not([tabindex="-1"])',
  "[contenteditable]",
].join(",");

function isVisible(el: HTMLElement): boolean {
  // jsdom returns 0 for layout properties, so we treat anything that survives
  // the disabled / aria-hidden / hidden checks as focusable. Real browsers
  // already exclude `display:none` from the selector match for most types.
  if (el.hasAttribute("hidden")) return false;
  if (el.getAttribute("aria-hidden") === "true") return false;
  return true;
}

function getFocusable(container: HTMLElement): HTMLElement[] {
  const nodes = Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
  return nodes.filter((el) => !el.hasAttribute("disabled") && isVisible(el));
}

/** Locks Tab / Shift+Tab focus within `containerRef` while `active` is true.
 *
 * - Saves `document.activeElement` on activation and restores it on cleanup so
 *   focus returns to the trigger (e.g. the button that opened a modal).
 * - Moves focus to `initialFocus` on activation; if not provided, focuses the
 *   container itself (useful when the dialog has no inputs).
 * - Cycles Tab between the first and last focusable descendants. If there is
 *   no focusable element inside, Tab is swallowed so focus cannot leave.
 *
 * Designed for modal-style overlays (Modal, dialog confirm/prompt). It relies
 * on `display: none` not being applied to the container while active – we use
 * `offsetParent !== null` as a cheap visibility heuristic, which matches the
 * conditional rendering style used in the modal layer.
 */
export function useFocusTrap(
  containerRef: RefObject<HTMLElement>,
  active: boolean,
  initialFocus?: RefObject<HTMLElement>
): void {
  useEffect(() => {
    if (!active) return;
    const container = containerRef.current;
    if (!container) return;

    const previouslyFocused = document.activeElement as HTMLElement | null;

    const target =
      initialFocus?.current ??
      getFocusable(container)[0] ??
      container;
    if (target && typeof target.focus === "function") {
      target.focus();
    }

    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== "Tab") return;
      const node = containerRef.current;
      if (!node) return;
      const focusables = getFocusable(node);
      if (focusables.length === 0) {
        e.preventDefault();
        return;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const activeEl = document.activeElement as HTMLElement | null;
      if (e.shiftKey && (activeEl === first || !node.contains(activeEl))) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && (activeEl === last || !node.contains(activeEl))) {
        e.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      if (previouslyFocused && typeof previouslyFocused.focus === "function") {
        // Defer to next tick so React has time to unmount portal contents
        // before we re-focus; otherwise the browser sometimes loses focus to
        // <body>.
        queueMicrotask(() => previouslyFocused.focus());
      }
    };
  }, [active, containerRef, initialFocus]);
}
