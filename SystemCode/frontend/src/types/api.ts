export type ApiErrorDetail = string | Array<{ loc: Array<string | number>; msg: string; type: string }>;
export type ApiErrorBody = { detail: ApiErrorDetail };

export type EmploymentType = "full_time" | "part_time" | "internship";
export type Degree = "bachelor" | "master" | "phd" | "diploma" | "not_applicable";
export type EducationEntryType = "degree" | "exchange";
export type ResearchType = "paper" | "patent" | "software_copyright" | "thesis" | "research_project" | "other";
export type WorkMode = "onsite" | "hybrid" | "remote";
export type TargetEmploymentType = "full_time" | "internship";

export type Experience = {
  company: string; title: string; employment_type: EmploymentType | null;
  start_date: string | null; end_date: string | null; description: string; country: string | null;
};
export type Project = {
  title: string; summary: string; technologies: string[]; role: string | null;
  start_date: string | null; end_date: string | null;
};
export type Research = {
  type: ResearchType; title: string; institution: string | null; summary: string;
  start_date: string | null; end_date: string | null;
};
export type Education = {
  institution: string; entry_type: EducationEntryType; degree: Degree; major: string | null;
  start_date: string | null; end_date: string | null; country: string | null;
  school_tier: string | null; research_direction: string | null; gpa: string | null;
  ranking: string | null; courses: string[];
};
export type Certificate = {
  name: string; issuer: string | null; issue_date: string | null; expiry_date: string | null; score: string | null;
};
export type SkillGroup = { category: string | null; description: string };
export type Award = { name: string; date: string | null };

export type ResumeDocument = {
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
  additional_info: string[];
};

export type JobSearchConstraints = {
  target_roles: string[];
  target_industries: string[];
  work_modes: WorkMode[];
  target_employment_types: TargetEmploymentType[];
  notes: string;
};

export type UserProfile = {
  resume: ResumeDocument;
  constraints: JobSearchConstraints;
  resume_upload_id: number | null;
  updated_at?: string;
};

export type SavedProfile = UserProfile & { updated_at: string };
export type ParsedResume = ResumeDocument & { about: string | null };
export type ResumeHistoryEntry = Pick<ResumeUpload, "id" | "filename" | "name" | "uploaded_at">;
export type ProfileOptions = {
  target_role_categories: Record<string, string[]>;
  target_industries: string[];
};

export type ResumeUpload = {
  id: number;
  filename: string;
  name: string | null;
  uploaded_at: string;
  resume: ParsedResume;
};

export type RankingJob = {
  rank: number;
  job_id: number;
  company: string;
  title: string;
  location: { city: string | null; country: string | null } | null;
  employment_type: string;
  final_score: number;
};

export type RankingResponse = {
  total_jobs: number;
  passed_count: number;
  returned_count: number;
  rejected_by_rule: Record<string, number>;
  results: RankingJob[];
};

export type JobMatchDetail = {
  job: {
    job_id: number; source: string; company: string; title: string;
    location: string | { city: string | null; country: string | null } | null;
    employment_type: string; url: string | null; description: string; summary: string;
    responsibilities: string[]; required_skills: string[]; preferred_skills: string[];
    collected_at: string | null;
  };
  match: Record<string, unknown> & { final_score: number; core_score?: number; preferred_skill_bonus?: number };
  recommendation: {
    level: "excellent" | "strong" | "moderate" | "developing" | string;
    level_label: string; summary: string; highlights: string[];
    evidence: Array<{
      requirement: string; candidate_evidence: string; evidence_source: string;
      match_type: string; similarity: number; relation: string | null; path: string[];
    }>;
  };
  gaps: Array<{
    name: string; gap_type: string; importance: string; current_evidence: string | null;
    reason: string; suggestion: string;
  }>;
  improvement_plan: {
    summary: string;
    priorities: Array<{ priority: "high" | "medium" | "low" | string; title: string; items: string[]; advice: string }>;
    next_action: string;
  };
};

export type InterviewQuestion = {
  sequence: number;
  id: number;
  question_type: "basic_programming" | "role_specific";
  allocated_role: string;
  question_text: string;
  standard_answer: string;
  question_text_en: string;
  standard_answer_en: string;
  difficulty_level: "easy" | "medium" | "hard" | "not_stated";
  roles: string[];
  source: string;
  company: string | null;
};

export type InterviewSample = {
  job_id: number;
  job_title: string;
  seed: number;
  generated_at: string;
  requested_count: number;
  returned_count: number;
  basic_question_count: number;
  difficulty_distribution: { easy: number; medium: number; hard: number };
  role_allocation: Array<{ role: string; similarity: number; normalized_weight: number; requested_quota: number; actual_count: number }>;
  questions: InterviewQuestion[];
  warnings: string[];
};

export type InterviewSampleRequest = {
  count?: number;
  difficulty_mix?: { easy: number; medium: number; hard: number };
  exclude_question_ids?: number[];
  seed?: number;
};

export type InterviewTranscription = {
  job_id: number;
  question_id: number;
  transcript: string;
  language: "en";
  model: string;
};

export type TargetJob = {
  job_id: number;
  title: string;
  company: string;
  location: unknown;
  url: string | null;
  match_score: number | null;
  stage: string;
  stage_note: string | null;
  interview_done_at: string | null;
  rewrite_status: "none" | "saved" | "stale";
  rewrite_updated_at: string | null;
  created_at: string;
  updated_at: string;
};

// 简历改写（对应后端 schemas/resume_rewrite.py）
export type LocalizedText = { en: string; zh: string };
export type RewriteSection = "experience" | "project" | "research" | "skills";
export type RewriteField = "description" | "summary" | "technologies" | "skill_groups";
export type RewriteValue = string | string[] | SkillGroup[];

export type RewriteReason = {
  issue_type: string;
  explanation: LocalizedText;
  guideline_keys: string[];
  jd_responsibility: string | null;
};

export type UserInputRequest = { placeholder: string; question: LocalizedText; reason: LocalizedText };

export type ResumeChange = {
  section: RewriteSection;
  index: number;
  field: RewriteField;
  original: RewriteValue;
  value: RewriteValue;
  reasons: RewriteReason[];
  needs_user_input: UserInputRequest[];
};

export type RewriteBlock = {
  section: RewriteSection;
  index: number;
  heading: string;
  status: "unchanged" | "rewritten" | "needs_input";
  changes: ResumeChange[];
  pending_inputs: UserInputRequest[];
  removed_skills: string[];
};

export type DeletionSuggestion = {
  section: "experience" | "project" | "research";
  index: number;
  line: number | null;
  original: string;
  reasons: RewriteReason[];
};

export type ResumeRewriteResult = {
  job_id: number | null;
  blocks: RewriteBlock[];
  rewritten_resume: ResumeDocument;
  deletion_suggestions: DeletionSuggestion[];
};

export type BlockFillRequest = {
  job_id: number;
  section: "experience" | "project" | "research";
  index: number;
  text: string;
  answers: Array<{ placeholder: string; answer: string | null }>;
};

export type BlockFillResult = {
  section: RewriteSection;
  index: number;
  field: RewriteField;
  value: string;
  needs_user_input: UserInputRequest[];
};

// 改写对比和审阅进度，后端原样存取（key 规则见 features/rewrite/assemble.ts 的 blockKey / draftKey）
export type RewriteSession = {
  result: ResumeRewriteResult;
  reviews: Record<string, "accepted" | "rejected">;
  drafts: Record<string, string>;
  pending: Record<string, UserInputRequest[]>;
  confirmed_deletions: Record<number, boolean>;
};

// resume 为 null = 只生成了改写对比、还没保存终稿
export type SavedResumeRewrite = { resume: ResumeDocument | null; session: RewriteSession | null; stale: boolean; updated_at: string };
