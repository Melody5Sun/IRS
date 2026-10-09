import type { MessageKey } from "../../i18n/en";
import type { UserProfile } from "../../types/api";
import { MONTH_PATTERN } from "./constants";

// id 对应表单字段的 DOM id（fld-<section>-<index>-<field>），用于定位与滚动
export type ValidationIssue = { id: string; section: string; message: MessageKey };

// 与后端 PUT /profile 的非空校验保持一致：选填字段（notes、expiry_date、major、role 等）不检查
export function validateProfile(profile: UserProfile): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const blank = (value: unknown) => value == null || (typeof value === "string" && !value.trim()) || (Array.isArray(value) && value.length === 0);
  const requireValue = (value: unknown, id: string, section: string, message: MessageKey) => {
    if (blank(value)) issues.push({ id, section, message });
  };
  const requireMonth = (value: string | null, id: string, section: string, message: MessageKey, after?: string | null) => {
    const text = String(value ?? "");
    if (/^\d{4}$/.test(text)) issues.push({ id, section, message: "profile.v.addMonth" });
    else if (!MONTH_PATTERN.test(text)) issues.push({ id, section, message });
    else if (after && MONTH_PATTERN.test(after) && text < after) issues.push({ id, section, message: "profile.v.beforeStart" });
  };

  requireValue(profile.resume.name, "fld-basic-0-name", "basic", "profile.v.fullName");
  requireValue(profile.resume.email, "fld-basic-0-email", "basic", "profile.v.email");
  requireValue(profile.resume.phone, "fld-basic-0-phone", "basic", "profile.v.phone");
  requireValue(profile.constraints.target_roles, "fld-intent-0-target_roles", "intent", "profile.v.targetRole");
  requireValue(profile.constraints.target_industries, "fld-intent-0-target_industries", "intent", "profile.v.targetIndustry");
  requireValue(profile.constraints.work_modes, "fld-intent-0-work_modes", "intent", "profile.v.workMode");
  requireValue(profile.constraints.target_employment_types, "fld-intent-0-target_employment_types", "intent", "profile.v.employmentType");

  if (!profile.resume.educations.length) issues.push({ id: "profile-educations", section: "educations", message: "profile.v.educationEntry" });
  profile.resume.educations.forEach((item, index) => {
    const prefix = `fld-educations-${index}`;
    requireValue(item.institution, `${prefix}-institution`, "educations", "profile.v.institution");
    requireValue(item.entry_type, `${prefix}-entry_type`, "educations", "profile.v.entryType");
    if (item.entry_type !== "exchange") requireValue(item.degree === "not_applicable" ? "" : item.degree, `${prefix}-degree`, "educations", "profile.v.degree");
    requireMonth(item.start_date, `${prefix}-start_date`, "educations", "profile.v.startDate");
    requireMonth(item.end_date, `${prefix}-end_date`, "educations", "profile.v.graduationDate", item.start_date);
    requireValue(item.country, `${prefix}-country`, "educations", "profile.v.country");
  });

  requireValue(profile.resume.skills, "fld-skills-0-skills", "skills", "profile.v.skill");
  requireValue(profile.resume.languages, "fld-skills-0-languages", "skills", "profile.v.language");
  profile.resume.skill_groups.forEach((item, index) => requireValue(item.description, `fld-skill_groups-${index}-description`, "skills", "profile.v.description"));

  profile.resume.experiences.forEach((item, index) => {
    const prefix = `fld-experiences-${index}`;
    requireValue(item.company, `${prefix}-company`, "experiences", "profile.v.company");
    requireValue(item.title, `${prefix}-title`, "experiences", "profile.v.title");
    requireValue(item.employment_type, `${prefix}-employment_type`, "experiences", "profile.v.experienceType");
    requireMonth(item.start_date, `${prefix}-start_date`, "experiences", "profile.v.startDate");
    if (item.end_date !== "present") requireMonth(item.end_date, `${prefix}-end_date`, "experiences", "profile.v.endDate", item.start_date);
    requireValue(item.country, `${prefix}-country`, "experiences", "profile.v.country");
    requireValue(item.description, `${prefix}-description`, "experiences", "profile.v.description");
  });
  profile.resume.projects.forEach((item, index) => {
    const prefix = `fld-projects-${index}`;
    requireValue(item.title, `${prefix}-title`, "projects", "profile.v.projectTitle");
    requireValue(item.summary, `${prefix}-summary`, "projects", "profile.v.summary");
    requireValue(item.technologies, `${prefix}-technologies`, "projects", "profile.v.technology");
  });
  profile.resume.research.forEach((item, index) => {
    const prefix = `fld-research-${index}`;
    requireValue(item.type, `${prefix}-type`, "research", "profile.v.researchType");
    requireValue(item.title, `${prefix}-title`, "research", "profile.v.title");
    requireValue(item.summary, `${prefix}-summary`, "research", "profile.v.summary");
  });
  profile.resume.certificates.forEach((item, index) => requireValue(item.name, `fld-certificates-${index}-name`, "certificates", "profile.v.certificateName"));
  profile.resume.awards.forEach((item, index) => requireValue(item.name, `fld-awards-${index}-name`, "certificates", "profile.v.awardName"));
  return issues;
}
