import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TagInput } from "./TagInput";

describe("TagInput", () => {
  it("renders pre-existing tags", () => {
    render(<TagInput value={["growth", "dividend"]} onChange={() => {}} />);
    expect(screen.getByText("growth")).toBeInTheDocument();
    expect(screen.getByText("dividend")).toBeInTheDocument();
  });

  it("normalises and adds a tag on Enter", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TagInput value={[]} onChange={onChange} />);

    const input = screen.getByRole("textbox");
    await user.type(input, "  Growth  {Enter}");

    expect(onChange).toHaveBeenCalledWith(["growth"]);
  });

  it("ignores duplicate tags", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TagInput value={["growth"]} onChange={onChange} />);

    const input = screen.getByRole("textbox");
    await user.type(input, "growth{Enter}");

    expect(onChange).not.toHaveBeenCalled();
  });

  it("removes the last tag on Backspace when input is empty", () => {
    const onChange = vi.fn();
    render(<TagInput value={["growth", "dividend"]} onChange={onChange} />);

    const input = screen.getByRole("textbox") as HTMLInputElement;
    input.focus();
    fireEvent.keyDown(input, { key: "Backspace" });

    expect(onChange).toHaveBeenCalledWith(["growth"]);
  });

  it("clicking the remove button removes the tag", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TagInput value={["growth", "dividend"]} onChange={onChange} />);

    await user.click(screen.getByLabelText("Tag growth entfernen"));
    expect(onChange).toHaveBeenCalledWith(["dividend"]);
  });

  it("comma triggers add", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TagInput value={[]} onChange={onChange} />);

    const input = screen.getByRole("textbox");
    await user.type(input, "value,");

    expect(onChange).toHaveBeenCalledWith(["value"]);
  });
});
