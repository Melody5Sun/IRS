import { describe, expect, it } from "vitest";
import { JOBS, QUESTIONS, REWRITE_BLOCKS } from "./data";

describe("frontend mock contracts", () => {
  it("uses unique job and question identifiers", () => {
    expect(new Set(JOBS.map((job) => job.id)).size).toBe(JOBS.length);
    expect(new Set(QUESTIONS.map((question) => question.id)).size).toBe(QUESTIONS.length);
  });

  it("provides data for every primary prototype workflow", () => {
    expect(JOBS.length).toBeGreaterThan(0);
    expect(QUESTIONS.length).toBeGreaterThan(0);
    expect(REWRITE_BLOCKS.length).toBeGreaterThan(0);
  });
});
