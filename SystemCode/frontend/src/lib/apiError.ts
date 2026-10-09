import type { ApiError } from "../api";

// 后端返回字符串 detail 时直接展示，否则用调用方给的兜底文案
export function detailOr(error: ApiError, fallback: string) {
  return typeof error.body.detail === "string" ? error.body.detail : fallback;
}
