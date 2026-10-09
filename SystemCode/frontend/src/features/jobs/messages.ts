import { ApiError } from "../../api";
import type { Translate } from "../../i18n/LanguageProvider";
import { detailOr } from "../../lib/apiError";

export type JobsErrorArea = "ranking" | "detail" | "target";

export function jobsErrorMessage(error: unknown, area: JobsErrorArea, t: Translate) {
  if (!(error instanceof ApiError)) return t("common.connectionError");
  if (error.status === 409 && area === "ranking") return t("jobs.error.profileRequired");
  if (error.status === 409 && area === "detail") return t("jobs.error.notAnalysed");
  if (error.status === 404 && area === "detail") return t("jobs.error.jobGone");
  if (error.status === 404 && area === "target") return t("jobs.error.targetMissing");
  return detailOr(error, t("common.requestFailed"));
}
