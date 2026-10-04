import { apiRequest } from "./client";
import type { TargetJob } from "../types/api";

export const targetsApi = {
  list: () => apiRequest<TargetJob[]>("/targets"),
  add: (jobId: number, matchScore?: number) => apiRequest<TargetJob>("/targets", { method: "POST", body: JSON.stringify({ job_id: jobId, match_score: matchScore }) }),
  update: (jobId: number, updates: { stage?: string; stage_note?: string; interview_done?: boolean }) => apiRequest<TargetJob>("/targets/" + jobId, { method: "PATCH", body: JSON.stringify(updates) }),
  remove: (jobId: number) => apiRequest<void>("/targets/" + jobId, { method: "DELETE" }),
};
