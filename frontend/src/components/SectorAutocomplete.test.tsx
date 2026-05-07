import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SectorAutocomplete } from "./SectorAutocomplete";

const suggestions = [
  { name: "Tech", count: 5 },
  { name: "Finance", count: 3 },
];

describe("SectorAutocomplete", () => {
  it("Dropdown erscheint bei Fokus wenn Vorschläge vorhanden sind", () => {
    render(
      <SectorAutocomplete value="" onChange={() => {}} suggestions={suggestions} />
    );

    const input = screen.getByRole("textbox");
    fireEvent.focus(input);

    expect(screen.getByRole("listbox")).toBeInTheDocument();
    expect(screen.getByText("Tech")).toBeInTheDocument();
    expect(screen.getByText("Finance")).toBeInTheDocument();
  });

  it("Dropdown verschwindet bei Blur", () => {
    vi.useFakeTimers();

    render(
      <SectorAutocomplete value="" onChange={() => {}} suggestions={suggestions} />
    );

    const input = screen.getByRole("textbox");
    fireEvent.focus(input);
    expect(screen.getByRole("listbox")).toBeInTheDocument();

    fireEvent.blur(input);
    act(() => {
      vi.advanceTimersByTime(150);
    });

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();

    vi.useRealTimers();
  });

  it("ArrowDown / ArrowUp navigiert durch die Vorschläge", () => {
    render(
      <SectorAutocomplete value="" onChange={() => {}} suggestions={suggestions} />
    );

    const input = screen.getByRole("textbox");
    fireEvent.focus(input);

    // Initial: erster Vorschlag ist aktiv (index 0 = "Tech")
    const options = screen.getAllByRole("option");
    expect(options[0]).toHaveAttribute("aria-selected", "true");
    expect(options[1]).toHaveAttribute("aria-selected", "false");

    // ArrowDown → index 1 = "Finance"
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(options[0]).toHaveAttribute("aria-selected", "false");
    expect(options[1]).toHaveAttribute("aria-selected", "true");

    // ArrowUp → zurück zu index 0 = "Tech"
    fireEvent.keyDown(input, { key: "ArrowUp" });
    expect(options[0]).toHaveAttribute("aria-selected", "true");
    expect(options[1]).toHaveAttribute("aria-selected", "false");
  });

  it("Enter übernimmt den hervorgehobenen Vorschlag und schließt das Dropdown", () => {
    const onChange = vi.fn();
    render(
      <SectorAutocomplete value="" onChange={onChange} suggestions={suggestions} />
    );

    const input = screen.getByRole("textbox");
    fireEvent.focus(input);

    // Erster Vorschlag ist aktiv (index 0 = "Tech")
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onChange).toHaveBeenCalledWith("Tech");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("Escape schließt das Dropdown ohne Wertänderung", () => {
    const onChange = vi.fn();
    render(
      <SectorAutocomplete value="" onChange={onChange} suggestions={suggestions} />
    );

    const input = screen.getByRole("textbox");
    fireEvent.focus(input);
    expect(screen.getByRole("listbox")).toBeInTheDocument();

    fireEvent.keyDown(input, { key: "Escape" });

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("Mausklick auf Vorschlag übernimmt den Wert", () => {
    const onChange = vi.fn();
    render(
      <SectorAutocomplete value="" onChange={onChange} suggestions={suggestions} />
    );

    const input = screen.getByRole("textbox");
    fireEvent.focus(input);

    const techOption = screen.getByText("Tech").closest("button")!;
    fireEvent.mouseDown(techOption);

    expect(onChange).toHaveBeenCalledWith("Tech");
  });

  it("disabled={true} deaktiviert das Input-Feld", () => {
    render(
      <SectorAutocomplete
        value=""
        onChange={() => {}}
        suggestions={suggestions}
        disabled={true}
      />
    );

    const input = screen.getByRole("textbox");
    expect(input).toBeDisabled();
  });

  it("suggestions={undefined} → kein Dropdown", () => {
    render(
      <SectorAutocomplete value="" onChange={() => {}} suggestions={undefined} />
    );

    const input = screen.getByRole("textbox");
    fireEvent.focus(input);

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });
});
