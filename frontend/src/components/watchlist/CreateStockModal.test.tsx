import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { CreateStockModal } from "./CreateStockModal";
import { api } from "../../api/client";

vi.mock("../../api/client", () => ({
  api: {
    post: vi.fn(),
  },
}));

vi.mock("../../lib/toast", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

const noop = async () => {};

describe("CreateStockModal", () => {
  beforeEach(() => {
    vi.mocked(api.post).mockReset();
  });

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

  // --- New tests for initialValues and isPending ---

  it("opens with empty fields when no initialValues are provided (backward compat)", () => {
    render(
      <CreateStockModal
        open={true}
        onClose={noop}
        tagSuggestions={[]}
        onCreated={noop}
      />
    );
    expect((screen.getByLabelText(/isin/i) as HTMLInputElement).value).toBe("");
    expect((screen.getByLabelText(/name/i) as HTMLInputElement).value).toBe("");
  });

  it("pre-fills ISIN and name fields when initialValues are provided", () => {
    render(
      <CreateStockModal
        open={true}
        onClose={noop}
        tagSuggestions={[]}
        onCreated={noop}
        initialValues={{ isin: "DE0007164600", name: "SAP SE" }}
      />
    );
    expect((screen.getByLabelText(/isin/i) as HTMLInputElement).value).toBe("DE0007164600");
    expect((screen.getByLabelText(/name/i) as HTMLInputElement).value).toBe("SAP SE");
  });

  it("re-seeds fields with new initialValues when modal is reopened", async () => {
    const { rerender } = render(
      <CreateStockModal
        open={false}
        onClose={noop}
        tagSuggestions={[]}
        onCreated={noop}
        initialValues={{ isin: "DE0007164600", name: "SAP SE" }}
      />
    );
    // Open with first target
    rerender(
      <CreateStockModal
        open={true}
        onClose={noop}
        tagSuggestions={[]}
        onCreated={noop}
        initialValues={{ isin: "DE0007164600", name: "SAP SE" }}
      />
    );
    expect((screen.getByLabelText(/isin/i) as HTMLInputElement).value).toBe("DE0007164600");

    // Close and reopen with different target
    rerender(
      <CreateStockModal
        open={false}
        onClose={noop}
        tagSuggestions={[]}
        onCreated={noop}
        initialValues={{ isin: "US0378331005", name: "Apple Inc." }}
      />
    );
    rerender(
      <CreateStockModal
        open={true}
        onClose={noop}
        tagSuggestions={[]}
        onCreated={noop}
        initialValues={{ isin: "US0378331005", name: "Apple Inc." }}
      />
    );
    expect((screen.getByLabelText(/isin/i) as HTMLInputElement).value).toBe("US0378331005");
    expect((screen.getByLabelText(/name/i) as HTMLInputElement).value).toBe("Apple Inc.");
  });

  it("disables the save button while the POST request is in flight", async () => {
    // Delay the POST so we can assert the pending state
    let resolvePost!: () => void;
    vi.mocked(api.post).mockReturnValueOnce(
      new Promise<{ data: unknown }>((res) => {
        resolvePost = () => res({ data: {} });
      })
    );

    render(
      <CreateStockModal
        open={true}
        onClose={noop}
        tagSuggestions={[]}
        onCreated={noop}
        initialValues={{ isin: "DE0007164600", name: "SAP SE" }}
      />
    );

    const saveBtn = screen.getByRole("button", { name: /speichern/i });
    fireEvent.click(saveBtn);

    // Button should be disabled and show loading label while pending
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /speichern…/i })).toBeDisabled()
    );

    // Resolve the POST so the component can clean up
    resolvePost();
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /speichern…/i })).not.toBeInTheDocument()
    );
  });

  it("calls onCreated and shows success toast after successful POST", async () => {
    const { toast } = await import("../../lib/toast");
    vi.mocked(api.post).mockResolvedValueOnce({ data: {} });
    const onCreated = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <CreateStockModal
        open={true}
        onClose={onClose}
        tagSuggestions={[]}
        onCreated={onCreated}
        initialValues={{ isin: "DE0007164600", name: "SAP SE" }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /speichern/i }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledOnce());
    expect(toast.success).toHaveBeenCalledWith("Unternehmen zur Watchlist hinzugefügt.");
  });

  it("re-enables the save button and keeps modal open after a failed POST", async () => {
    vi.mocked(api.post).mockRejectedValueOnce({
      response: { data: { detail: "Conflict" } },
    });

    render(
      <CreateStockModal
        open={true}
        onClose={noop}
        tagSuggestions={[]}
        onCreated={noop}
        initialValues={{ isin: "DE0007164600", name: "SAP SE" }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /speichern/i }));

    // Error shown, modal still open, button re-enabled
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Conflict")
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^speichern$/i })).not.toBeDisabled();
  });
});
