import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Modal } from "./Modal";

describe("Modal — bottomSheet variant", () => {
  it("renders with bottom-sheet CSS class", () => {
    render(
      <Modal open onClose={() => {}} title="Filter" variant="bottomSheet">
        <p>Inhalt</p>
      </Modal>
    );
    expect(document.querySelector(".modal-card--bottom-sheet")).toBeInTheDocument();
    expect(document.querySelector(".modal-backdrop--bottom")).toBeInTheDocument();
  });

  it("renders the drag handle", () => {
    render(
      <Modal open onClose={() => {}} title="Filter" variant="bottomSheet">
        <p>Inhalt</p>
      </Modal>
    );
    expect(document.querySelector(".modal-drag-handle")).toBeInTheDocument();
  });

  it("renders title in the header", () => {
    render(
      <Modal open onClose={() => {}} title="Mein Filter" variant="bottomSheet">
        <p>Inhalt</p>
      </Modal>
    );
    expect(screen.getByText("Mein Filter")).toBeInTheDocument();
  });

  it("calls onClose when Escape is pressed", () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="Filter" variant="bottomSheet">
        <p>Inhalt</p>
      </Modal>
    );
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when close button is clicked", () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="Filter" variant="bottomSheet">
        <p>Inhalt</p>
      </Modal>
    );
    fireEvent.click(screen.getByLabelText("Schließen"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("renders nothing when open is false", () => {
    render(
      <Modal open={false} onClose={() => {}} title="Filter" variant="bottomSheet">
        <p>Inhalt</p>
      </Modal>
    );
    expect(screen.queryByText("Filter")).not.toBeInTheDocument();
    expect(document.querySelector(".modal-card--bottom-sheet")).not.toBeInTheDocument();
  });

  it("renders center variant without bottom-sheet classes by default", () => {
    render(
      <Modal open onClose={() => {}} title="Center">
        <p>Inhalt</p>
      </Modal>
    );
    expect(document.querySelector(".modal-card--bottom-sheet")).not.toBeInTheDocument();
    expect(document.querySelector(".modal-card")).toBeInTheDocument();
  });

  it("renders footer when provided", () => {
    render(
      <Modal
        open
        onClose={() => {}}
        title="Filter"
        variant="bottomSheet"
        footer={<button type="button">Zurücksetzen</button>}
      >
        <p>Inhalt</p>
      </Modal>
    );
    expect(screen.getByRole("button", { name: "Zurücksetzen" })).toBeInTheDocument();
  });
});
