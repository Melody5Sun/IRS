import { apiRequest } from "./client";
import type { JobMatchDetail, RankingResponse, UserProfile } from "../types/api";

export const jobsApi = {
  getLibraryStatus: () => apiRequest<{ synced_at: string | null; active_job_count: number }>("/jobs/library-status"),
  rank: () => apiRequest<RankingResponse>("/ranking", { method: "POST" }),
  getMatchDetail: (jobId: number, profile: UserProfile) => apiRequest<JobMatchDetail>("/jobs/" + jobId + "/match-detail", { method: "POST", body: JSON.stringify(profile) }),
};
