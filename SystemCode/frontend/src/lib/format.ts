import type { Lang } from "../i18n/LanguageProvider";

const LOCALES: Record<Lang, string> = { en: "en-SG", zh: "zh-CN" };

export function localeOf(lang: Lang) {
  return LOCALES[lang];
}

// 例：8 Oct 2026, 10:00 —— 画像页的上传/保存时间
export function formatDateTime(value: string, lang: Lang) {
  return new Intl.DateTimeFormat(LOCALES[lang], { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

// 例：8 Oct 2026 —— 岗位采集日期、目标岗位添加日期
export function formatDay(value: string, lang: Lang) {
  return new Intl.DateTimeFormat(LOCALES[lang], { day: "numeric", month: "short", year: "numeric" }).format(new Date(value));
}

// 后端的 location 可能是字符串、{city, country} 或空；没有可展示内容时返回 null，由调用方给出"未注明"文案
export function locationLabel(location: unknown): string | null {
  if (!location) return null;
  if (typeof location === "string") return location;
  if (typeof location === "object") {
    const value = location as { city?: unknown; country?: unknown };
    const parts = [value.city, value.country].filter((part): part is string => typeof part === "string" && Boolean(part.trim()));
    return [...new Set(parts.map((part) => part.trim()))].join(", ") || null;
  }
  return null;
}
