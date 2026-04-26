import { describe, expect, it } from "vitest";

import { createStockSchema, editStockSchema } from "./stockFormSchemas";
import { validateSchema } from "./validation";

describe("createStockSchema", () => {
  it("flags empty ISIN and name", () => {
    const errors = validateSchema(
      { isin: "", name: "", currency: "", tranches: "" },
      createStockSchema
    );
    expect(errors.isin).toBeTruthy();
    expect(errors.name).toBeTruthy();
    expect(errors.tranches).toBeUndefined();
  });

  it("rejects ISIN of wrong length", () => {
    const errors = validateSchema(
      { isin: "DE12345", name: "x", currency: "", tranches: "" },
      createStockSchema
    );
    expect(errors.isin).toContain("12");
  });

  it("rejects non-alphanumeric ISIN characters", () => {
    const errors = validateSchema(
      { isin: "DE-007164600", name: "x", currency: "", tranches: "" },
      createStockSchema
    );
    expect(errors.isin).toBeTruthy();
  });

  it("accepts a valid stock", () => {
    const errors = validateSchema(
      {
        isin: "DE0007164600",
        name: "Siemens AG",
        currency: "EUR",
        tranches: "3",
      },
      createStockSchema
    );
    expect(errors).toEqual({});
  });

  it("accepts blank tranches but rejects garbage tranches", () => {
    expect(
      validateSchema(
        { isin: "DE0007164600", name: "Siemens", currency: "", tranches: "" },
        createStockSchema
      )
    ).toEqual({});
    expect(
      validateSchema(
        { isin: "DE0007164600", name: "Siemens", currency: "", tranches: "-1" },
        createStockSchema
      ).tranches
    ).toBeTruthy();
  });
});

describe("editStockSchema", () => {
  const empty = {
    name: "",
    currency: "",
    tranches: "",
    ticker_override: "",
    link_yahoo: "",
    link_finanzen: "",
    link_onvista_chart: "",
    link_onvista_fundamental: "",
  };

  it("requires only the name", () => {
    const errors = validateSchema(empty, editStockSchema);
    expect(errors.name).toBeTruthy();
    expect(errors.currency).toBeUndefined();
    expect(errors.tranches).toBeUndefined();
    expect(errors.link_yahoo).toBeUndefined();
  });

  it("validates URL fields when filled in", () => {
    const errors = validateSchema(
      { ...empty, name: "x", link_yahoo: "not a url" },
      editStockSchema
    );
    expect(errors.link_yahoo).toBeTruthy();
  });

  it("accepts well-formed URLs", () => {
    const errors = validateSchema(
      {
        ...empty,
        name: "x",
        link_yahoo: "https://finance.yahoo.com/quote/SIE.DE",
      },
      editStockSchema
    );
    expect(errors.link_yahoo).toBeUndefined();
  });

  it("validates ticker shape", () => {
    expect(
      validateSchema({ ...empty, name: "x", ticker_override: "SIE.DE" }, editStockSchema)
        .ticker_override
    ).toBeUndefined();
    expect(
      validateSchema({ ...empty, name: "x", ticker_override: "BRK-B" }, editStockSchema)
        .ticker_override
    ).toBeUndefined();
    expect(
      validateSchema(
        { ...empty, name: "x", ticker_override: "ab cd" },
        editStockSchema
      ).ticker_override
    ).toBeTruthy();
  });
});
