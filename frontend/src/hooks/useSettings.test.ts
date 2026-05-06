import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { useSettings } from "./useSettings";

// JSDOM does not implement URL.createObjectURL — stub it so downloadBlob works.
Object.defineProperty(URL, "createObjectURL", { value: vi.fn(() => "blob:mock"), writable: true });
Object.defineProperty(URL, "revokeObjectURL", { value: vi.fn(), writable: true });

vi.mock("../api/client", () => ({
  api: {
    get: vi.fn(),
    put: vi.fn(),
    post: vi.fn(),
  },
}));

import { api } from "../api/client";

// Helper to build a minimal Blob-like response as the real downloadBlob
// helper does `res.data instanceof Blob ? res.data : new Blob([res.data])`.
function _blobResponse(content = "a,b\n1,2") {
  return { data: new Blob([content], { type: "text/csv" }) };
}

const mockSettings = {
  update_hour: 22,
  update_minute: 30,
  update_weekends: false,
  ai_provider: "openai",
  ai_endpoint: null,
  ai_model: "gpt-4o-mini",
  ai_refresh_interval: "monthly",
  ai_api_key_set: true,
  jobs_enabled: true,
  jobs_update_hour: 2,
  jobs_update_minute: 0,
};

describe("useSettings", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.mocked(api.get).mockResolvedValue({ data: mockSettings });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("loads settings on mount", async () => {
    const { result } = renderHook(() => useSettings());

    expect(result.current.settings).toBeNull();

    await waitFor(() => expect(result.current.settings).not.toBeNull());
    expect(result.current.settings?.ai_provider).toBe("openai");
  });

  it("isDirty is false when nothing has changed", async () => {
    const { result } = renderHook(() => useSettings());
    await waitFor(() => expect(result.current.settings).not.toBeNull());
    expect(result.current.isDirty).toBe(false);
  });

  it("isDirty becomes true when settings change", async () => {
    const { result } = renderHook(() => useSettings());
    await waitFor(() => expect(result.current.settings).not.toBeNull());

    act(() => {
      result.current.setSettings((prev) =>
        prev ? { ...prev, update_weekends: true } : prev
      );
    });

    expect(result.current.isDirty).toBe(true);
  });

  it("isDirty becomes true when apiKey has a value", async () => {
    const { result } = renderHook(() => useSettings());
    await waitFor(() => expect(result.current.settings).not.toBeNull());

    act(() => {
      result.current.setApiKey("sk-newkey");
    });

    expect(result.current.isDirty).toBe(true);
  });

  it("discardChanges resets state to initial values", async () => {
    const { result } = renderHook(() => useSettings());
    await waitFor(() => expect(result.current.settings).not.toBeNull());

    act(() => {
      result.current.setSettings((prev) =>
        prev ? { ...prev, update_weekends: true } : prev
      );
      result.current.setApiKey("sk-newkey");
    });

    expect(result.current.isDirty).toBe(true);

    act(() => {
      result.current.discardChanges();
    });

    expect(result.current.isDirty).toBe(false);
    expect(result.current.apiKey).toBe("");
    expect(result.current.settings?.update_weekends).toBe(false);
  });

  it("loadError is set when the API call fails", async () => {
    vi.mocked(api.get).mockRejectedValueOnce({
      response: { data: { detail: "server error" } },
    });
    const { result } = renderHook(() => useSettings());
    await waitFor(() => expect(result.current.loadError).not.toBeNull());
    expect(result.current.loadError).toContain("server error");
  });

  describe("downloadJobHistory", () => {
    it("calls the export endpoint and sets ok feedback", async () => {
      vi.mocked(api.get)
        .mockResolvedValueOnce({ data: mockSettings })   // initial settings load
        .mockResolvedValueOnce(_blobResponse());          // export-csv call

      const { result } = renderHook(() => useSettings());
      await waitFor(() => expect(result.current.settings).not.toBeNull());

      await act(async () => {
        await result.current.downloadJobHistory();
      });

      const exportCall = vi.mocked(api.get).mock.calls.find((c) =>
        (c[0] as string).includes("history/export-csv")
      );
      expect(exportCall).toBeDefined();
      expect(result.current.feedback?.kind).toBe("ok");
      expect(result.current.feedback?.text).toContain("Job-Historie exportiert");
    });

    it("sets error feedback when the export call fails", async () => {
      vi.mocked(api.get)
        .mockResolvedValueOnce({ data: mockSettings })
        .mockRejectedValueOnce({ response: { data: { detail: "forbidden" } } });

      const { result } = renderHook(() => useSettings());
      await waitFor(() => expect(result.current.settings).not.toBeNull());

      await act(async () => {
        await result.current.downloadJobHistory();
      });

      expect(result.current.feedback?.kind).toBe("error");
    });
  });

  describe("uploadJobHistory", () => {
    const _okReport = {
      total_rows: 5,
      inserted: 4,
      skipped_existing: 1,
      unmapped_rows: [],
      malformed_rows: [],
    };

    it("calls the import endpoint and sets ok feedback when no warnings", async () => {
      vi.mocked(api.post).mockResolvedValueOnce({ data: _okReport });

      const { result } = renderHook(() => useSettings());
      await waitFor(() => expect(result.current.settings).not.toBeNull());

      const file = new File(["job_source_id,isin,source_name,snapshot_date,jobs_count\n"], "job-history.csv", {
        type: "text/csv",
      });

      await act(async () => {
        await result.current.uploadJobHistory(file);
      });

      expect(vi.mocked(api.post)).toHaveBeenCalledWith(
        "/job-sources/history/import-csv",
        expect.any(FormData),
        expect.objectContaining({ headers: expect.objectContaining({ "Content-Type": "multipart/form-data" }) })
      );
      expect(result.current.feedback?.kind).toBe("ok");
      expect(result.current.feedback?.text).toContain("4 eingefügt");
      expect(result.current.feedback?.text).toContain("1 übersprungen");
    });

    it("sets error-kind feedback when unmapped rows exist", async () => {
      vi.mocked(api.post).mockResolvedValueOnce({
        data: {
          total_rows: 2,
          inserted: 1,
          skipped_existing: 0,
          unmapped_rows: [{ row: {}, reason: "no match" }],
          malformed_rows: [],
        },
      });

      const { result } = renderHook(() => useSettings());
      await waitFor(() => expect(result.current.settings).not.toBeNull());

      const file = new File([""], "job-history.csv", { type: "text/csv" });

      await act(async () => {
        await result.current.uploadJobHistory(file);
      });

      expect(result.current.feedback?.kind).toBe("error");
      expect(result.current.feedback?.text).toContain("1 nicht zugeordnet");
    });

    it("sets error feedback when the API call fails", async () => {
      vi.mocked(api.post).mockRejectedValueOnce({
        response: { data: { detail: "server error" } },
      });

      const { result } = renderHook(() => useSettings());
      await waitFor(() => expect(result.current.settings).not.toBeNull());

      const file = new File([""], "job-history.csv", { type: "text/csv" });

      await act(async () => {
        await result.current.uploadJobHistory(file);
      });

      expect(result.current.feedback?.kind).toBe("error");
    });
  });
});
