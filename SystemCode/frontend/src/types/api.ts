export type ApiErrorDetail = string | Array<{ loc: Array<string | number>; msg: string; type: string }>;
export type ApiErrorBody = { detail: ApiErrorDetail };

export type ResumeDocument = {
  name: string | null;
  email: string | null;
  phone: string | null;
  experiences: Array<Record<string, unknown>>;
  projects: Array<Record<string, unknown>>;
  research: Array<Record<string, unknown>>;
  skills: string[];
  skill_groups: Array<Record<string, unknown>>;
  educations: Array<Record<string, unknown>>;
  certificates: Array<Record<string, unknown>>;
  languages: string[];
  awards: Array<Record<string, unknown>>;
  additional_info: string[];
};

export type JobSearchConstraints = {
  target_roles: string[];
  target_industries: string[];
  work_modes: Array<"onsite" | "hybrid" | "remote">;
  target_employment_types: Array<"full_time" | "internship">;
  notes: string;
};

export type UserProfile = {
  resume: ResumeDocument;
  constraints: JobSearchConstraints;
  resume_upload_id: number;
  updated_at?: string;
};

export type ResumeUpload = {
  id: number;
  filename: string;
  name: string | null;
  uploaded_at: string;
  resume: ResumeDocument & { about?: string | null };
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
  job: Record<string, unknown> & { job_id: number; company: string; title: string; url: string | null };
  match: Record<string, unknown> & { final_score: number };
  recommendation: { level: string; level_label: string; summary: string; highlights: string[]; evidence: Array<Record<string, unknown>> };
  gaps: Array<Record<string, unknown>>;
  improvement_plan: Record<string, unknown>;
};

export type InterviewQuestion = {
  sequence: number;
  id: number;
  question_type: "basic_programming" | "role_specific";
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
  questions: InterviewQuestion[];
  warnings: string[];
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
