import { beforeEach, describe, expect, it } from "vitest";
import { getCurrentProfile, getResumeHistory, saveParsedResume } from "./profileStorage";
import type { ResumeDocument } from "../types/profile";

function fakeResume(name: string): ResumeDocument {
  return {
    name,
    email: null,
    phone: null,
    experiences: [],
    projects: [],
    research: [],
    skills: [],
    skill_groups: [],
    educations: [],
    certificates: [],
    languages: [],
    awards: [],
    additional_info: [],
  };
}

beforeEach(() => {
  localStorage.clear();
});

describe("profileStorage", () => {
  it("首次上传简历时，画像专属字段（constraints）全部为空", () => {
    const profile = saveParsedResume(fakeResume("Jane"));
    expect(profile.constraints).toEqual({
      target_roles: [],
      target_industries: [],
      work_modes: [],
      target_employment_types: [],
      notes: "",
    });
  });

  it("已经填过 constraints 时，重新上传简历会保留这些值", () => {
    saveParsedResume(fakeResume("Jane"));
    const store = JSON.parse(localStorage.getItem("careerpilot:profile")!);
    store.profile.constraints.notes = "求职中";
    localStorage.setItem("careerpilot:profile", JSON.stringify(store));

    const updated = saveParsedResume(fakeResume("Jane v2"));

    expect(updated.constraints.notes).toBe("求职中");
    expect(getCurrentProfile()?.resume.name).toBe("Jane v2");
  });

  it("连续上传超过 3 次后，历史记录恒为 3 条且最新在前", () => {
    saveParsedResume(fakeResume("A"));
    saveParsedResume(fakeResume("B"));
    saveParsedResume(fakeResume("C"));
    saveParsedResume(fakeResume("D"));

    const history = getResumeHistory();
    expect(history).toHaveLength(3);
    expect(history.map((p) => p.resume.name)).toEqual(["D", "C", "B"]);
  });
});
