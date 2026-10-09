import { describe, expect, it } from "vitest";
import type { DeletionSuggestion, ResumeChange, ResumeDocument, ResumeRewriteResult } from "../../types/api";
import { buildFinalResume, draftKey } from "./assemble";

const reason = { issue_type: "weak_action_verb", explanation: { en: "e", zh: "z" }, guideline_keys: [], jd_responsibility: null };
const experience = (company: string, description: string) => ({ company, title: "Intern", employment_type: null, start_date: null, end_date: null, description, country: null });

// 改写结果：经历 0 已改好（rewritten，已写进 rewritten_resume）；项目 0 待补充（needs_input，rewritten_resume 里仍是原文）
function sample(): ResumeRewriteResult {
  const rewritten: ResumeDocument = {
    name: "A", email: null, phone: null,
    experiences: [experience("X", "Built payment APIs"), experience("Y", "Line one\nLine two")],
    projects: [{ title: "P", summary: "Made a tool", technologies: ["Go", "SQL"], role: null, start_date: null, end_date: null }],
    research: [], skills: [], skill_groups: [{ category: null, description: "Go" }], educations: [],
    certificates: [], languages: [], awards: [], additional_info: [],
  };
  const expChange: ResumeChange = { section: "experience", index: 0, field: "description", original: "Did APIs", value: "Built payment APIs", reasons: [reason], needs_user_input: [] };
  const projChange: ResumeChange = { section: "project", index: 0, field: "summary", original: "Made a tool", value: "Built a tool for [users]", reasons: [reason], needs_user_input: [] };
  const techChange: ResumeChange = { section: "project", index: 0, field: "technologies", original: ["SQL", "Go"], value: ["Go", "SQL"], reasons: [reason], needs_user_input: [] };
  return {
    job_id: 1,
    rewritten_resume: rewritten,
    deletion_suggestions: [],
    blocks: [
      { section: "experience", index: 0, heading: "Intern · X", status: "rewritten", changes: [expChange], pending_inputs: [], removed_skills: [] },
      { section: "project", index: 0, heading: "P", status: "needs_input", changes: [projChange, techChange], pending_inputs: [], removed_skills: [] },
    ],
  };
}

describe("buildFinalResume", () => {
  it("keeps accepted rewrites and writes back filled or edited drafts", () => {
    const result = sample();
    const project = result.blocks[1];
    const resume = buildFinalResume(result, { "experience:0": "accepted", "project:0": "accepted" }, { [draftKey(project, 0)]: "Built a tool for 200 users" }, []);
    expect(resume.experiences[0].description).toBe("Built payment APIs");
    expect(resume.projects[0].summary).toBe("Built a tool for 200 users");
    expect(resume.projects[0].technologies).toEqual(["Go", "SQL"]);
  });

  it("restores the original text of rejected blocks without touching the input", () => {
    const result = sample();
    const resume = buildFinalResume(result, { "experience:0": "rejected", "project:0": "rejected" }, {}, []);
    expect(resume.experiences[0].description).toBe("Did APIs");
    expect(resume.projects[0].technologies).toEqual(["SQL", "Go"]);
    expect(result.rewritten_resume.experiences[0].description).toBe("Built payment APIs");
  });

  it("deletes confirmed lines by content and whole entries from the end", () => {
    const result = sample();
    const deletions: DeletionSuggestion[] = [
      { section: "experience", index: 1, line: 3, original: "Line two", reasons: [reason] },
      { section: "experience", index: 0, line: null, original: "Built payment APIs", reasons: [reason] },
      { section: "experience", index: 1, line: 0, original: "Not in the text", reasons: [reason] },
    ];
    const resume = buildFinalResume(result, { "experience:0": "accepted" }, {}, deletions);
    expect(resume.experiences).toHaveLength(1);
    expect(resume.experiences[0]).toMatchObject({ company: "Y", description: "Line one" });
  });
});
