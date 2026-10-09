import { ApiError } from "../../api";
import type { Translate } from "../../i18n/LanguageProvider";

export type ProfileAction = "load" | "upload" | "save";
export type ProfileFailure = { reason: unknown; action: ProfileAction };

export function profileErrorMessage({ reason, action }: ProfileFailure, t: Translate) {
  if (!(reason instanceof ApiError)) return t("common.connectionError");
  if (action === "upload" && reason.status === 400) return t("profile.error.pdfOnly");
  if (action === "upload" && reason.status === 422) return t("profile.error.noText");
  if (action === "upload" && reason.status === 503) return t("profile.error.llmMissing");
  if (reason.status === 502) return action === "upload" ? t("profile.error.parseUnavailable") : t("profile.error.aiUnavailable");
  if (reason.status === 422) return t("profile.error.incomplete");
  if (reason.status === 404 && action === "save") return t("profile.error.uploadMissing");
  return action === "load" ? t("profile.error.loadFailed") : t("common.requestFailed");
}
