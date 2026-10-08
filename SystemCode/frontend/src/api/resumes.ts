import { apiRequest } from "./client";
import type { ResumeDocument, ResumeHistoryEntry, ResumeUpload } from "../types/api";

export const resumesApi = {
  parsePdf: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return apiRequest<ResumeUpload>("/resumes/parse-pdf", { method: "POST", body });
  },
  getHistory: () => apiRequest<ResumeHistoryEntry[]>("/resumes/history"),
  getHistoryItem: (id: number) => apiRequest<ResumeUpload>("/resumes/history/" + id),
  generateRewrite: (jobId: number) => apiRequest<Record<string, unknown>>("/resumes/rewrite", { method: "POST", body: JSON.stringify({ job_id: jobId }) }),
  fillRewriteBlock: (payload: Record<string, unknown>) => apiRequest<Record<string, unknown>>("/resumes/rewrite/fill", { method: "POST", body: JSON.stringify(payload) }),
  getSavedRewrite: (jobId: number) => apiRequest<{ resume: ResumeDocument; stale: boolean; updated_at: string }>("/resumes/rewrites/" + jobId),
  saveRewrite: (jobId: number, resume: ResumeDocument) => apiRequest<{ resume: ResumeDocument; stale: boolean; updated_at: string }>("/resumes/rewrites/" + jobId, { method: "PUT", body: JSON.stringify(resume) }),
};
