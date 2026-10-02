// 与后端 Pydantic schema 手动保持一致：
// SystemCode/backend/app/schemas/resume.py、SystemCode/backend/app/schemas/profile.py

// 简历经历的工作类型
export type EmploymentType = "full_time" | "part_time" | "internship";
export type Degree = "bachelor" | "master" | "phd" | "diploma" | "not_applicable";
export type EducationEntryType = "degree" | "exchange";
export type ResearchType = "paper" | "patent" | "software_copyright" | "thesis" | "research_project" | "other";
export type WorkMode = "onsite" | "hybrid" | "remote";
export type TargetEmploymentType = "full_time" | "internship";

export interface Experience {
  company: string;
  title: string;
  // null = 解析时没判断出来；保存画像前必须由用户选择
  employment_type: EmploymentType | null;
  start_date: string | null;
  end_date: string | null;
  description: string;
  country: string | null;
}

export interface Project {
  title: string;
  summary: string;
  technologies: string[];
  role: string | null;
  start_date: string | null;
  end_date: string | null;
}

export interface Research {
  type: ResearchType;
  title: string;
  institution: string | null;
  summary: string;
  start_date: string | null;
  end_date: string | null;
}

export interface Education {
  institution: string;
  entry_type: EducationEntryType;
  degree: Degree;
  major: string | null;
  start_date: string | null;
  end_date: string | null;
  country: string | null;
  school_tier: string | null;
  research_direction: string | null;
  gpa: string | null;
  ranking: string | null;
  courses: string[];
}

export interface Certificate {
  name: string;
  issuer: string | null;
  issue_date: string | null;
  expiry_date: string | null;
  score: string | null;
}

// 技能栏原文的一行，供简历改写使用；匹配用扁平的 skills
export interface SkillGroup {
  category: string | null;
  description: string;
}

export interface Award {
  name: string;
  date: string | null;
}

// POST /api/resumes/parse-pdf 的响应体形状
export interface ResumeDocument {
  name: string | null;
  email: string | null;
  phone: string | null;
  experiences: Experience[];
  projects: Project[];
  research: Research[];
  skills: string[];
  skill_groups: SkillGroup[];
  educations: Education[];
  certificates: Certificate[];
  languages: string[];
  awards: Award[];
  // 没有专门字段的简历内容，"Label: value" 形式
  additional_info: string[];
}

// 画像专属、简历里没有的求职约束字段
export interface JobSearchConstraints {
  target_roles: string[];
  target_industries: string[];
  work_modes: WorkMode[];
  target_employment_types: TargetEmploymentType[];
  notes: string;
}

// 对应后端 UserProfile：画像 = 简历 + 求职约束
export interface Profile {
  resume: ResumeDocument;
  constraints: JobSearchConstraints;
}

export function emptyConstraints(): JobSearchConstraints {
  return { target_roles: [], target_industries: [], work_modes: [], target_employment_types: [], notes: "" };
}

// GET /api/profile/options 的响应体形状，供目标岗位/行业下拉框渲染
export interface ProfileOptions {
  target_role_categories: Record<string, string[]>;
  target_industries: string[];
}
