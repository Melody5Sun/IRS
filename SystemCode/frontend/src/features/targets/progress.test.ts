import { describe, expect, it } from "vitest";
import { translate } from "../../i18n/LanguageProvider";
import type { TargetJob } from "../../types/api";
import { APPLIED_STAGES, averageProgress, completedSteps, progressLabel, stageLabel } from "./progress";

const target = (overrides: Partial<TargetJob>): TargetJob => ({
  job_id: 1, title: "T", company: "C", location: null, url: null, match_score: null, stage: "not_applied", stage_note: null,
  interview_done_at: null, rewrite_status: "none", rewrite_updated_at: null, created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z",
  ...overrides,
});

describe("target progress", () => {
  it("counts the matched step for every target and adds rewrite, interview and application", () => {
    expect(completedSteps(target({}))).toBe(1);
    expect(completedSteps(target({ rewrite_status: "stale", interview_done_at: "2026-10-02T00:00:00Z", stage: "offer" }))).toBe(4);
  });

  it("averages progress as a percentage", () => {
    expect(averageProgress([])).toBe(0);
    expect(averageProgress([target({}), target({ rewrite_status: "saved" })])).toBe(38);
  });

  it("prefers the user's own progress note and offers every stage after submitting", () => {
    const t = (key: Parameters<typeof translate>[1]) => translate("en", key);
    expect(progressLabel(target({ stage: "interview_1", stage_note: "  " }), t)).toBe(stageLabel("interview_1", t));
    expect(progressLabel(target({ stage: "interview_1", stage_note: "Waiting for HR" }), t)).toBe("Waiting for HR");
    expect(APPLIED_STAGES).toEqual(["submitted", "written_test", "interview_1", "interview_2", "interview_3", "hr_interview", "manager_interview", "offer", "rejected"]);
  });

  it("translates known stages and keeps unknown ones", () => {
    expect(stageLabel("interview_1", (key) => translate("zh", key))).toBe("一面");
    expect(stageLabel("assessment_centre", (key) => translate("en", key))).toBe("assessment_centre");
  });
});
