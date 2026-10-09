import { describe, expect, it } from "vitest";
import type { UserProfile } from "../../types/api";
import { emptyProfile } from "./constants";
import { validateProfile } from "./validation";

function completeProfile(): UserProfile {
  const profile = emptyProfile();
  profile.resume = {
    ...profile.resume,
    name: "Alex", email: "alex@example.com", phone: "123",
    skills: ["Python"], languages: ["English"],
    educations: [{ ...profile.resume.educations[0], institution: "NUS", degree: "master", start_date: "2025-08", end_date: "2026-12", country: "Singapore" }],
  };
  profile.constraints = { target_roles: ["Backend Developer"], target_industries: ["Internet"], work_modes: ["hybrid"], target_employment_types: ["internship"], notes: "" };
  return profile;
}

describe("validateProfile", () => {
  it("accepts a complete profile with only optional fields empty", () => {
    expect(validateProfile(completeProfile())).toEqual([]);
  });

  it("reports every required field of an empty draft with field ids", () => {
    const ids = validateProfile(emptyProfile()).map((issue) => issue.id);
    expect(ids).toContain("fld-basic-0-name");
    expect(ids).toContain("fld-intent-0-work_modes");
    expect(ids).toContain("fld-educations-0-degree");
    expect(ids).toContain("fld-skills-0-languages");
  });

  it("checks month format and date order", () => {
    const profile = completeProfile();
    profile.resume.educations[0] = { ...profile.resume.educations[0], start_date: "2025", end_date: "2024-01" };
    // 只有年份时提示补月份；开始时间无效时不做先后比较
    expect(validateProfile(profile)).toEqual([{ id: "fld-educations-0-start_date", section: "educations", message: "profile.v.addMonth" }]);
    profile.resume.educations[0] = { ...profile.resume.educations[0], start_date: "2025-08", end_date: "2024-01" };
    expect(validateProfile(profile)).toEqual([{ id: "fld-educations-0-end_date", section: "educations", message: "profile.v.beforeStart" }]);
  });

  it("skips the degree for exchange entries and the end date for current jobs", () => {
    const profile = completeProfile();
    profile.resume.educations[0] = { ...profile.resume.educations[0], entry_type: "exchange", degree: "not_applicable" };
    profile.resume.experiences = [{ company: "Acme", title: "Intern", employment_type: "internship", start_date: "2026-01", end_date: "present", description: "APIs", country: "SG" }];
    expect(validateProfile(profile)).toEqual([]);
  });
});
