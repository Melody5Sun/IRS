import { Select } from "../../components/common/Select";
import { useI18n } from "../../i18n/LanguageProvider";
import { LEVELS, type JobFilter, type MinimumLevel } from "./recommendation";

type Props = {
  filter: JobFilter;
  onFilter: (filter: JobFilter) => void;
  minimumLevel: MinimumLevel;
  onMinimumLevel: (level: MinimumLevel) => void;
  counts: Record<JobFilter, number>;
  filteredCount: number;
};

const FILTER_KEYS = { all: "jobs.filter.all", internship: "jobs.filter.internship", full_time: "jobs.filter.fullTime" } as const;
// "limited" 是最低档，选它等于不过滤，所以下拉里不单独列出
const LEVEL_OPTIONS = ["potential", "recommended", "highly"] as const;

export function JobFilters({ filter, onFilter, minimumLevel, onMinimumLevel, counts, filteredCount }: Props) {
  const { t } = useI18n();
  return (
    <div className="job-tools recommendations-tools">
      <div className="seg" aria-label={t("jobs.filter.label")}>
        {(Object.keys(FILTER_KEYS) as JobFilter[]).map((value) => (
          <button key={value} className={filter === value ? "active" : ""} onClick={() => onFilter(value)}>{t(FILTER_KEYS[value], { count: counts[value] })}</button>
        ))}
      </div>
      <label className="recommendation-level-filter">
        <span>{t("jobs.minimumLevel")}</span>
        <Select value={minimumLevel} aria-label={t("jobs.minimumLevel")} onChange={(level) => onMinimumLevel(level as MinimumLevel)}
          options={[{ value: "all", label: t("jobs.allLevels") }, ...LEVEL_OPTIONS.map((level) => ({ value: level, label: t(LEVELS[level].labelKey) }))]} />
      </label>
      <span>{t("jobs.eligibleCount", { count: filteredCount })}</span>
    </div>
  );
}
