import { apiRequest } from "./client";
import type { InterviewSample, InterviewSampleRequest, InterviewTranscription } from "../types/api";

export const interviewApi = {
  sample: (jobId: number, request: InterviewSampleRequest = {}) =>
    apiRequest<InterviewSample>(`/jobs/${jobId}/interview-questions/sample`, {
      method: "POST",
      body: JSON.stringify(request),
    }),
  transcribe: (jobId: number, questionId: number, audio: Blob) => {
    const form = new FormData();
    form.append("audio", audio, "interview-answer.webm");
    return apiRequest<InterviewTranscription>(`/jobs/${jobId}/interview-questions/${questionId}/transcription`, {
      method: "POST",
      body: form,
    });
  },
};
