import { describe, expect, it } from "vitest";

import { extractApiError } from "./apiError";

describe("extractApiError", () => {
  it("returns the fallback when error is falsy", () => {
    expect(extractApiError(null, "fallback")).toBe("fallback");
    expect(extractApiError(undefined, "fallback")).toBe("fallback");
  });

  it("returns string errors as-is", () => {
    expect(extractApiError("nope", "fallback")).toBe("nope");
  });

  it("extracts FastAPI string detail", () => {
    const err = { response: { data: { detail: "Already taken" } } };
    expect(extractApiError(err, "fallback")).toBe("Already taken");
  });

  it("joins FastAPI validation errors", () => {
    const err = {
      response: {
        data: {
          detail: [
            { loc: ["body", "isin"], msg: "field required", type: "value_error" },
            { loc: ["body", "name"], msg: "string too short", type: "value_error" },
          ],
        },
      },
    };
    expect(extractApiError(err, "fallback")).toBe("field required | string too short");
  });

  it("falls back to a plain `message` field", () => {
    const err = { response: { data: { message: "Server boom" } } };
    expect(extractApiError(err, "fallback")).toBe("Server boom");
  });

  it("falls back to error.message when no body details exist", () => {
    const err = { message: "Network error" };
    expect(extractApiError(err, "fallback")).toBe("Network error");
  });

  it("returns the fallback when nothing useful is available", () => {
    expect(extractApiError({ response: { data: {} } }, "fallback")).toBe("fallback");
  });

  it("ignores non-string detail entries", () => {
    const err = { response: { data: { detail: [{ foo: "bar" }] } } };
    expect(extractApiError(err, "fallback")).toBe("fallback");
  });
});
