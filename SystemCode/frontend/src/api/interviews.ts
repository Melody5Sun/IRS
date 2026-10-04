import { apiRequest } from "./client";
import type { InterviewSample } from "../types/api";

export const interviewsApi = {
  sample: (jobId: number, options: Record<string, unknown> = {}) => apiRequest<InterviewSample>("/jobs/" + jobId + "/interview-questions/sample", { method: "POST", body: JSON.stringify(options) }),
  transcribe: (jobId: number, questionId: number, audio: File | Blob) => {
    const body = new FormData();
    body.append("audio", audio);
    return apiRequest<{ job_id: number; question_id: number; transcript: string; language: "en"; model: string }>("/jobs/" + jobId + "/interview-questions/" + questionId + "/transcription", { method: "POST", body });
  },
};
