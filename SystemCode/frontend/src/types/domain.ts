export type Page =
  | "dashboard"
  | "profile"
  | "jobs"
  | "rewrite"
  | "interview"
  | "targets";

export type Job = {
  id: number;
  score: number;
  title: string;
  company: string;
  location: string;
  type: string;
  summary: string;
  skills: string[];
  strengths: string[];
  gaps: string[];
};

export type InterviewQuestion = {
  id: number;
  difficulty: "Easy" | "Medium" | "Hard";
  type: "Basic programming" | "Role specific";
  text: string;
  answer: string;
};

export type ResumeRewriteBlock = {
  title: string;
  original: string;
  revised: string;
  reason: string;
};
