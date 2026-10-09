import { apiRequest } from "./client";
import type { BlockFillRequest, BlockFillResult, ResumeDocument, ResumeHistoryEntry, ResumeRewriteResult, ResumeUpload, SavedResumeRewrite } from "../types/api";

export const resumesApi = {
  parsePdf: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return apiRequest<ResumeUpload>("/resumes/parse-pdf", { method: "POST", body });
  },
  getHistory: () => apiRequest<ResumeHistoryEntry[]>("/resumes/history"),
  getHistoryItem: (id: number) => apiRequest<ResumeUpload>("/resumes/history/" + id),
  generateRewrite: (jobId: number) => apiRequest<ResumeRewriteResult>("/resumes/rewrite", { method: "POST", body: JSON.stringify({ job_id: jobId }) }),
  fillRewriteBlock: (payload: BlockFillRequest) => apiRequest<BlockFillResult>("/resumes/rewrite/fill", { method: "POST", body: JSON.stringify(payload) }),
  getSavedRewrite: (jobId: number) => apiRequest<SavedResumeRewrite>("/resumes/rewrites/" + jobId),
  saveRewrite: (jobId: number, resume: ResumeDocument) => apiRequest<SavedResumeRewrite>("/resumes/rewrites/" + jobId, { method: "PUT", body: JSON.stringify(resume) }),
};
