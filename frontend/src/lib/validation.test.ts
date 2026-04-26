import { describe, expect, it } from "vitest";

import {
  chain,
  currencyCode,
  exactLength,
  isin,
  maxLength,
  nonNegativeInt,
  oneOf,
  optional,
  pattern,
  required,
  url,
  validateSchema,
} from "./validation";

describe("required", () => {
  it("rejects empty and whitespace-only strings", () => {
    expect(required()("")).toBeTruthy();
    expect(required()("   ")).toBeTruthy();
    expect(required("custom")("")).toBe("custom");
  });

  it("accepts any non-blank string", () => {
    expect(required()("a")).toBeNull();
    expect(required()(" hello ")).toBeNull();
  });
});

describe("exactLength", () => {
  it("checks length, not trim()", () => {
    expect(exactLength(3)("abc")).toBeNull();
    expect(exactLength(3)("ab")).toBeTruthy();
    expect(exactLength(3)(" ab")).toBeNull();
  });
});

describe("maxLength", () => {
  it("allows values up to the limit", () => {
    expect(maxLength(5)("12345")).toBeNull();
    expect(maxLength(5)("123456")).toBeTruthy();
  });
});

describe("pattern", () => {
  it("uses the provided RegExp and message", () => {
    const v = pattern(/^[A-Z]+$/, "Nur Großbuchstaben.");
    expect(v("ABC")).toBeNull();
    expect(v("Abc")).toBe("Nur Großbuchstaben.");
  });
});

describe("isin", () => {
  it("accepts well-formed ISIN strings", () => {
    expect(isin()("DE0007164600")).toBeNull();
    expect(isin()("US0378331005")).toBeNull();
  });

  it("rejects wrong length or characters", () => {
    expect(isin()("DE000716460")).toBeTruthy(); // 11 chars
    expect(isin()("DE000716460A0")).toBeTruthy(); // 13 chars
    expect(isin()("de0007164600")).toBeNull(); // lowercase is upper-cased before test
    expect(isin()("DE-007164600")).toBeTruthy(); // dash is not [A-Z0-9]
  });
});

describe("currencyCode", () => {
  it("requires three uppercase letters", () => {
    expect(currencyCode()("EUR")).toBeNull();
    expect(currencyCode()("eur")).toBeNull(); // upper-cased internally
    expect(currencyCode()("EU")).toBeTruthy();
    expect(currencyCode()("EURO")).toBeTruthy();
    expect(currencyCode()("E1R")).toBeTruthy();
  });
});

describe("nonNegativeInt", () => {
  it("rejects empty, negative, and non-integer values", () => {
    expect(nonNegativeInt()("")).toBeTruthy();
    expect(nonNegativeInt()("-1")).toBeTruthy();
    expect(nonNegativeInt()("1.5")).toBeTruthy();
    expect(nonNegativeInt()("abc")).toBeTruthy();
  });

  it("accepts zero and positive integers", () => {
    expect(nonNegativeInt()("0")).toBeNull();
    expect(nonNegativeInt()("42")).toBeNull();
    expect(nonNegativeInt()(" 7 ")).toBeNull();
  });
});

describe("url", () => {
  it("accepts http and https URLs", () => {
    expect(url()("https://example.com")).toBeNull();
    expect(url()("http://localhost:8080/path?q=1")).toBeNull();
  });

  it("rejects empty, whitespace, and other protocols", () => {
    expect(url()("")).toBeTruthy();
    expect(url()("   ")).toBeTruthy();
    expect(url()("ftp://example.com")).toBeTruthy();
    expect(url()("javascript:alert(1)")).toBeTruthy();
    expect(url()("not a url")).toBeTruthy();
  });
});

describe("oneOf", () => {
  it("checks membership in the allowed list", () => {
    const v = oneOf(["a", "b", "c"]);
    expect(v("a")).toBeNull();
    expect(v("d")).toBeTruthy();
  });
});

describe("optional", () => {
  it("skips validation for empty / whitespace values", () => {
    const v = optional(currencyCode());
    expect(v("")).toBeNull();
    expect(v("   ")).toBeNull();
    expect(v("EUR")).toBeNull();
    expect(v("EU")).toBeTruthy();
  });
});

describe("chain", () => {
  it("returns the first error and short-circuits", () => {
    const v = chain(required("req"), exactLength(2, "len"));
    expect(v("")).toBe("req");
    expect(v("a")).toBe("len");
    expect(v("ab")).toBeNull();
  });

  it("returns null when no validators error", () => {
    expect(chain(required(), exactLength(2))("ab")).toBeNull();
  });
});

describe("validateSchema", () => {
  it("collects only fields that error, keyed by field", () => {
    interface Form {
      a: string;
      b: string;
    }
    const errors = validateSchema<Form>(
      { a: "", b: "ok" },
      { a: required("a is required"), b: required("b is required") }
    );
    expect(errors).toEqual({ a: "a is required" });
  });

  it("returns an empty object when all validators pass", () => {
    expect(validateSchema({ x: "ok" }, { x: required() })).toEqual({});
  });

  it("ignores fields without a validator", () => {
    expect(validateSchema({ x: "", y: "ok" }, { y: required() })).toEqual({});
  });
});
