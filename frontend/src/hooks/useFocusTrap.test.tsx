import { fireEvent, render } from "@testing-library/react";
import { useRef } from "react";
import { describe, expect, it } from "vitest";

import { useFocusTrap } from "./useFocusTrap";

interface HarnessProps {
  active: boolean;
}

function Harness({ active }: HarnessProps) {
  const ref = useRef<HTMLDivElement>(null);
  useFocusTrap(ref, active);
  return (
    <>
      <button data-testid="outside-before">outside before</button>
      <div ref={ref} tabIndex={-1} data-testid="trap">
        <button data-testid="first">first</button>
        <button data-testid="middle">middle</button>
        <button data-testid="last">last</button>
      </div>
      <button data-testid="outside-after">outside after</button>
    </>
  );
}

describe("useFocusTrap", () => {
  it("focuses the first focusable child when activated", () => {
    const { getByTestId } = render(<Harness active={true} />);
    expect(document.activeElement).toBe(getByTestId("first"));
  });

  it("wraps focus from last back to first on Tab", () => {
    const { getByTestId } = render(<Harness active={true} />);
    const last = getByTestId("last");
    last.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(getByTestId("first"));
  });

  it("wraps focus from first back to last on Shift+Tab", () => {
    const { getByTestId } = render(<Harness active={true} />);
    const first = getByTestId("first");
    first.focus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(getByTestId("last"));
  });

  it("returns focus to the previously focused element on deactivation", () => {
    const trigger = document.createElement("button");
    trigger.textContent = "trigger";
    document.body.appendChild(trigger);
    trigger.focus();
    expect(document.activeElement).toBe(trigger);

    const { rerender } = render(<Harness active={true} />);
    rerender(<Harness active={false} />);

    return Promise.resolve().then(() => {
      expect(document.activeElement).toBe(trigger);
      trigger.remove();
    });
  });

  it("does not steal focus while inactive", () => {
    const trigger = document.createElement("button");
    document.body.appendChild(trigger);
    trigger.focus();
    render(<Harness active={false} />);
    expect(document.activeElement).toBe(trigger);
    trigger.remove();
  });
});
