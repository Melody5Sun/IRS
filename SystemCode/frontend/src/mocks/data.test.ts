import { describe, expect, it } from "vitest";
import { JOBS, REWRITE_BLOCKS } from "./data";

describe("frontend mock contracts", () => {
  it("uses unique job identifiers", () => {
    expect(new Set(JOBS.map((job) => job.id)).size).toBe(JOBS.length);
  });

  it("provides data for every primary prototype workflow", () => {
    expect(JOBS.length).toBeGreaterThan(0);
    expect(REWRITE_BLOCKS.length).toBeGreaterThan(0);
  });
});
