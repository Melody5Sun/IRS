import type { MessageKey } from "../../i18n/en";
import type { JobSearchConstraints, ResumeDocument, UserProfile } from "../../types/api";

export type ListKey = "experiences" | "projects" | "research" | "educations" | "certificates" | "skill_groups" | "awards";
export type Option = readonly [value: string, labelKey: MessageKey];

// 必填项未完成时的提示色：首次保存前为琥珀色，点过保存后转为红色
export const TODO_AMBER = "#8a6a3b";
export const ERROR_RED = "#9d3a2c";
export const MONTH_PATTERN = /^\d{4}-\d{2}$/;

export const EMPTY_CONSTRAINTS: JobSearchConstraints = {
  target_roles: [], target_industries: [], work_modes: [],
  target_employment_types: [], notes: "",
};

const EMPTY_EDUCATION = { institution: "", entry_type: "degree", degree: "not_applicable", major: "", start_date: "", end_date: "", country: "", school_tier: "", research_direction: "", gpa: "", ranking: "", courses: [] } as const;

export const EMPTY_RESUME: ResumeDocument = {
  name: "", email: "", phone: "", experiences: [], projects: [], research: [],
  skills: [], skill_groups: [],
  educations: [{ ...EMPTY_EDUCATION, courses: [] }],
  certificates: [], languages: [], awards: [], additional_info: [],
};

export const NEW_ITEMS: Record<ListKey, Record<string, unknown>> = {
  experiences: { company: "", title: "", employment_type: null, start_date: "", end_date: "", description: "", country: "" },
  projects: { title: "", summary: "", technologies: [], role: "", start_date: "", end_date: "" },
  research: { type: "research_project", title: "", institution: "", summary: "", start_date: "", end_date: "" },
  educations: { ...EMPTY_EDUCATION, courses: [] },
  certificates: { name: "", issuer: "", issue_date: "", expiry_date: "", score: "" },
  skill_groups: { category: "", description: "" },
  awards: { name: "", date: "" },
};

// 没有已保存画像时的初始草稿（深拷贝，避免改到常量）
export function emptyProfile(): UserProfile {
  return { resume: { ...EMPTY_RESUME, educations: EMPTY_RESUME.educations.map((item) => ({ ...item, courses: [] })) }, constraints: { ...EMPTY_CONSTRAINTS }, resume_upload_id: null };
}

export const DEGREE_OPTIONS: Option[] = [
  ["bachelor", "profile.degree.bachelor"], ["master", "profile.degree.master"], ["phd", "profile.degree.phd"],
  ["diploma", "profile.degree.diploma"], ["not_applicable", "profile.degree.notApplicable"],
];
export const ENTRY_TYPE_OPTIONS: Option[] = [["degree", "profile.entryType.degree"], ["exchange", "profile.entryType.exchange"]];
export const EMPLOYMENT_OPTIONS: Option[] = [
  ["full_time", "common.employment.fullTime"], ["part_time", "common.employment.partTime"], ["internship", "common.employment.internship"],
];
export const TARGET_EMPLOYMENT_OPTIONS: Option[] = [["full_time", "common.employment.fullTime"], ["internship", "common.employment.internship"]];
export const WORK_MODE_OPTIONS: Option[] = [["onsite", "profile.workMode.onsite"], ["hybrid", "profile.workMode.hybrid"], ["remote", "profile.workMode.remote"]];
export const RESEARCH_TYPE_OPTIONS: Option[] = [
  ["paper", "profile.researchType.paper"], ["patent", "profile.researchType.patent"], ["software_copyright", "profile.researchType.softwareCopyright"],
  ["thesis", "profile.researchType.thesis"], ["research_project", "profile.researchType.researchProject"], ["other", "profile.researchType.other"],
];
// 语言名作为数据提交，保持英文
export const QUICK_LANGUAGES = ["English", "Mandarin", "Malay", "Tamil", "Cantonese"];
