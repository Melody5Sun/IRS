import { ApiError } from "../../api";
import type { Translate } from "../../i18n/LanguageProvider";
import { detailOr } from "../../lib/apiError";

// device 表示摄像头/麦克风授权失败，其余都是接口错误
export type InterviewFailure = { reason: unknown; device?: "camera" | "microphone" };

export function interviewErrorMessage({ reason, device }: InterviewFailure, t: Translate) {
  if (device) return reason instanceof Error ? reason.message : t(device === "camera" ? "interview.error.camera" : "interview.error.microphone");
  if (!(reason instanceof ApiError)) return t("common.connectionError");
  if (reason.status === 409) return t("interview.error.noRole");
  if (reason.status === 413) return t("interview.error.tooLarge");
  if (reason.status === 422) return t("interview.error.badFormat");
  if (reason.status === 503) return t("interview.error.notConfigured");
  if (reason.status === 502) return t("interview.error.unavailable");
  return detailOr(reason, t("common.requestFailed"));
}
