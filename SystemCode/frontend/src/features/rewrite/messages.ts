import { ApiError } from "../../api";
import type { Translate } from "../../i18n/LanguageProvider";
import { detailOr } from "../../lib/apiError";

export function rewriteErrorMessage(reason: unknown, t: Translate) {
  if (!(reason instanceof ApiError)) return t("common.connectionError");
  if (reason.status === 502) return t("rewrite.error.llm");
  if (reason.status === 503) return t("rewrite.error.notConfigured");
  // 409 有多种原因（没有画像 / 不是目标岗位 / 还有待补充的占位），后端 detail 已写明
  return detailOr(reason, t("common.requestFailed"));
}
