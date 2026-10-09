import { useGo } from "../../app/routes";
import { useI18n } from "../../i18n/LanguageProvider";
import { locationLabel } from "../../lib/format";
import type { JobMatchDetail, RankingJob, TargetJob } from "../../types/api";
import { MatchDetail } from "./MatchDetail";
import { employmentLabel, LEVELS, recommendationLevel } from "./recommendation";

type Props = {
  job: RankingJob;
  target?: TargetJob;
  detail?: JobMatchDetail;
  detailError?: string;
  open: boolean;
  loadingDetail: boolean;
  updatingTarget: boolean;
  showTargetPanel: boolean;
  onToggleDetail: () => void;
  onSelectTarget: () => void;
  onCloseTargetPanel: () => void;
  onRequestRemove: (target: TargetJob) => void;
};

export function JobCard(props: Props) {
  const { job, target, detail, open, loadingDetail, updatingTarget } = props;
  const { t } = useI18n();
  const go = useGo();
  const level = recommendationLevel(job.final_score);

  return (
    <article className="job recommendation-job">
      <div className={`recommendation-level ${level}`}><strong>{t(LEVELS[level].labelKey)}</strong><span>{t("jobs.recommendation")}</span></div>
      <div className="job-main">
        <h2>{job.title}</h2>
        <small>{job.company} · {locationLabel(job.location) ?? t("common.locationNotStated")} · {employmentLabel(job.employment_type, t)}</small>
        <p>{detail?.recommendation.summary ?? t("jobs.summaryPlaceholder")}</p>
        {detail && <div className="tags">
          {detail.job.required_skills.map((skill) => <em key={skill}>{skill}</em>)}
          {detail.job.preferred_skills.map((skill) => <em className="preferred" key={skill}>{t("jobs.preferredSkill", { skill })}</em>)}
        </div>}
      </div>
      <div className="job-actions">
        <button className="secondary" disabled={loadingDetail} onClick={props.onToggleDetail}>{loadingDetail ? t("jobs.loadingMatch") : open ? t("jobs.hideDetails") : t("jobs.viewMatch")}</button>
        <button className="primary" disabled={updatingTarget} onClick={props.onSelectTarget}>{updatingTarget ? t("jobs.updating") : target ? t("jobs.targetAdded") : t("jobs.setTarget")}</button>
      </div>

      {props.showTargetPanel && target && <div className="target-action-panel">
        <p>{t("jobs.targetPanel.text")}</p>
        <button className="primary" onClick={() => go("targets")}>{t("jobs.targetPanel.view")}</button>
        <button className="secondary" onClick={() => props.onRequestRemove(target)}>{t("jobs.targetPanel.remove")}</button>
        <button className="ghost" onClick={props.onCloseTargetPanel}>{t("common.cancel")}</button>
      </div>}

      {open && <MatchDetail detail={detail} loading={loadingDetail} error={props.detailError} />}
    </article>
  );
}
