import { describe, expect, it } from "vitest";
import { translate } from "../../i18n/LanguageProvider";
import type { RankingJob } from "../../types/api";
import { employmentLabel, filterJobs, matchTypeLabel, recommendationLevel } from "./recommendation";

const job = (job_id: number, employment_type: string, final_score: number): RankingJob => ({ rank: job_id, job_id, company: "C", title: "T", location: null, employment_type, final_score });

describe("recommendation helpers", () => {
  it("maps scores to levels at the documented thresholds", () => {
    expect([0, 14.9, 15, 29.9, 30, 49.9, 50, 90].map(recommendationLevel)).toEqual(["limited", "limited", "potential", "potential", "recommended", "recommended", "highly", "highly"]);
  });

  it("filters by employment type and minimum level", () => {
    const jobs = [job(1, "internship", 60), job(2, "full_time", 35), job(3, "internship", 10)];
    expect(filterJobs(jobs, "all", "all").map((item) => item.job_id)).toEqual([1, 2, 3]);
    expect(filterJobs(jobs, "internship", "all").map((item) => item.job_id)).toEqual([1, 3]);
    expect(filterJobs(jobs, "all", "recommended").map((item) => item.job_id)).toEqual([1, 2]);
  });

  it("labels known enums and humanizes unknown ones", () => {
    const t = (lang: "en" | "zh") => (key: Parameters<typeof translate>[1]) => translate(lang, key);
    expect(employmentLabel("full_time", t("en"))).toBe("Full-time");
    expect(employmentLabel("full_time", t("zh"))).toBe("全职");
    expect(employmentLabel("contract_role", t("en"))).toBe("contract role");
    expect(matchTypeLabel("semantic_match")).toBe("Semantic Match");
  });
});
