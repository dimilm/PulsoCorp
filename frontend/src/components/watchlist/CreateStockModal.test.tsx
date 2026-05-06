import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CreateStockModal } from "./CreateStockModal";
import { api } from "../../api/client";

vi.mock("../../api/client", () => ({
  api: {
    post: vi.fn(),
  },
}));

const noop = async () => {};

describe("CreateStockModal", () => {
  it("renders nothing when closed", () => {
    const { container } = render(
      <CreateStockModal
        open={false}
        onClose={noop}
        tagSuggestions={[]}
        onCreated={noop}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the form when open", () => {
    render(
      <CreateStockModal
        open={true}
        onClose={noop}
        tagSuggestions={[]}
        onCreated={noop}
      />
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Unternehmen hinzufügen")).toBeInTheDocument();
  });

  it("calls onClose when Abbrechen is clicked", async () => {
    const onClose = vi.fn();
    render(
      <CreateStockModal
        open={true}
        onClose={onClose}
        tagSuggestions={[]}
        onCreated={noop}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: /abbrechen/i }));
    await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
  });

  it("shows an error message when the API call fails", async () => {
    vi.mocked(api.post).mockRejectedValueOnce({
      response: { data: { detail: "ISIN already exists" } },
    });

    render(
      <CreateStockModal
        open={true}
        onClose={noop}
        tagSuggestions={[]}
        onCreated={noop}
      />
    );

    fireEvent.change(screen.getByLabelText(/isin/i), { target: { value: "US0378331005" } });
    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: "Apple Inc." } });

    fireEvent.click(screen.getByRole("button", { name: /speichern/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("ISIN already exists")
    );
  });
});
