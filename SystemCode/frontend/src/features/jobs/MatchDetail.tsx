import { useI18n } from "../../i18n/LanguageProvider";
import { formatDay } from "../../lib/format";
import type { JobMatchDetail } from "../../types/api";
import { humanize, matchTypeLabel, sourceLabel } from "./recommendation";

// 展开后的匹配详情：左侧简历证据，右侧差距与下一步建议
export function MatchDetail({ detail, loading, error }: { detail?: JobMatchDetail; loading: boolean; error?: string }) {
  const { lang, t } = useI18n();
  return (
    <div className="match recommendation-match">
      {loading && <div className="match-loading">{t("jobs.detail.loading")}</div>}
      {error && <div className="match-loading error">{error}</div>}
      {detail && <>
        <section>
          <h3>{t("jobs.detail.evidenceTitle")}</h3>
          {detail.recommendation.evidence.length ? detail.recommendation.evidence.map((evidence, index) => (
            <div className="evidence-row" key={`${evidence.requirement}-${index}`}>
              <strong>{t("jobs.detail.requirement", { text: evidence.requirement })}</strong>
              <p>{t("jobs.detail.resumeEvidence", { text: evidence.candidate_evidence })}</p>
              <small>{sourceLabel(evidence.evidence_source, t)} · {matchTypeLabel(evidence.match_type)} · {t("jobs.detail.confidence", { percent: Math.round(evidence.similarity * 100) })}</small>
            </div>
          )) : <p className="empty-detail">{t("jobs.detail.noEvidence")}</p>}
        </section>
        <section>
          <h3>{t("jobs.detail.gapsTitle")}</h3>
          {detail.gaps.length ? detail.gaps.map((gap, index) => (
            <div className="gap-row" key={`${gap.name}-${index}`}>
              <div><em>{humanize(gap.gap_type)}</em><strong>{gap.name}</strong></div>
              <p>{gap.suggestion || gap.reason}</p>
            </div>
          )) : <p className="empty-detail">{t("jobs.detail.noGaps")}</p>}
          <div className="improvement-note">
            <strong>{t("jobs.detail.nextStep")}</strong>
            <p>{detail.improvement_plan.summary}</p>
            {detail.improvement_plan.next_action && <p>{detail.improvement_plan.next_action}</p>}
          </div>
          <small className="job-source-note">{t("jobs.detail.source", {
            date: detail.job.collected_at ? formatDay(detail.job.collected_at, lang) : t("jobs.detail.dateNotStated"),
            responsibilities: detail.job.responsibilities.length,
            skills: detail.job.required_skills.length + detail.job.preferred_skills.length,
          })}</small>
        </section>
        {detail.job.url && <footer><a className="secondary job-link" href={detail.job.url} target="_blank" rel="noreferrer">{t("jobs.detail.openApplication")}</a></footer>}
      </>}
    </div>
  );
}
