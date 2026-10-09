import { describe, expect, it } from "vitest";
import { locationLabel } from "./format";

describe("locationLabel", () => {
  it("handles strings, objects and empty values", () => {
    expect(locationLabel("Singapore")).toBe("Singapore");
    expect(locationLabel({ city: "Singapore", country: "Singapore" })).toBe("Singapore");
    expect(locationLabel({ city: " ", country: "SG" })).toBe("SG");
    expect(locationLabel({ city: null, country: null })).toBeNull();
    expect(locationLabel(null)).toBeNull();
  });
});
