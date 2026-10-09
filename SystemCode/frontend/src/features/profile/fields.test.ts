import { describe, expect, it } from "vitest";
import { filterSuggestions } from "./fields";

describe("filterSuggestions", () => {
  const countries = ["China", "Indonesia", "Singapore", "Taiwan"];

  it("lists everything when empty or when the input already is an option", () => {
    expect(filterSuggestions(countries, " ")).toEqual(countries);
    expect(filterSuggestions(countries, "china")).toEqual(countries);
  });

  it("matches case-insensitively and puts prefix matches first", () => {
    expect(filterSuggestions(countries, "IN")).toEqual(["Indonesia", "China", "Singapore"]);
    expect(filterSuggestions(countries, "xyz")).toEqual([]);
  });
});
