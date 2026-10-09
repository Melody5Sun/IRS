import type { Translate } from "../../i18n/LanguageProvider";
import type { MessageKey } from "../../i18n/en";
import type { RankingJob } from "../../types/api";

export type JobFilter = "all" | "internship" | "full_time";
export type LevelKey = "limited" | "potential" | "recommended" | "highly";
export type MinimumLevel = "all" | LevelKey;

export const PER_PAGE = 10;

export const LEVELS: Record<LevelKey, { labelKey: MessageKey; rank: number }> = {
  limited: { labelKey: "jobs.level.limited", rank: 0 },
  potential: { labelKey: "jobs.level.potential", rank: 1 },
  recommended: { labelKey: "jobs.level.recommended", rank: 2 },
  highly: { labelKey: "jobs.level.highly", rank: 3 },
};

// 推荐等级阈值（final_score 为 0–100）
export function recommendationLevel(score: number): LevelKey {
  if (score >= 50) return "highly";
  if (score >= 30) return "recommended";
  if (score >= 15) return "potential";
  return "limited";
}

export function filterJobs(jobs: RankingJob[], filter: JobFilter, minimumLevel: MinimumLevel) {
  return jobs.filter((job) => {
    const matchesType = filter === "all" || job.employment_type === filter;
    const matchesLevel = minimumLevel === "all" || LEVELS[recommendationLevel(job.final_score)].rank >= LEVELS[minimumLevel].rank;
    return matchesType && matchesLevel;
  });
}

const EMPLOYMENT_KEYS: Record<string, MessageKey> = {
  full_time: "common.employment.fullTime",
  part_time: "common.employment.partTime",
  internship: "common.employment.internship",
};

const SOURCE_KEYS: Record<string, MessageKey> = {
  skills: "jobs.source.skills",
  experience: "jobs.source.experience",
  project: "jobs.source.project",
  research: "jobs.source.research",
  career_intent: "jobs.source.careerIntent",
};

// 后端枚举值没有对应文案时，把下划线换成空格原样展示
export const humanize = (value: string) => value.split("_").join(" ");

export function employmentLabel(value: string, t: Translate) {
  const key = EMPLOYMENT_KEYS[value];
  return key ? t(key) : humanize(value);
}

export function sourceLabel(value: string, t: Translate) {
  const key = SOURCE_KEYS[value];
  return key ? t(key) : humanize(value);
}

export function matchTypeLabel(value: string) {
  return humanize(value).replace(/\b\w/g, (letter: string) => letter.toUpperCase());
}
