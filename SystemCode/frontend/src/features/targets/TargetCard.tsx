import { useNavigate } from "react-router-dom";
import { ROUTES, useGo } from "../../app/routes";
import { ProgressStep } from "../../components/common/ProgressStep";
import { useI18n } from "../../i18n/LanguageProvider";
import { formatDay, locationLabel } from "../../lib/format";
import type { TargetJob } from "../../types/api";
import { completedSteps, stageLabel } from "./progress";

export function TargetCard({ target }: { target: TargetJob }) {
  const { lang, t } = useI18n();
  const go = useGo();
  const navigate = useNavigate();
  const completed = completedSteps(target);
  const progress = completed * 25;
  const stage = stageLabel(target.stage, t);
  const rewriteDetail = target.rewrite_status === "stale" ? t("targets.rewriteStale") : target.rewrite_status === "saved" ? t("targets.rewriteSaved") : t("targets.rewriteNone");

  return (
    <article className="target">
      <header>
        <div className="score"><strong>{target.match_score == null ? "—" : Math.round(target.match_score)}</strong><span>{t("targets.match")}</span></div>
        <div><h2>{target.title}</h2><small>{target.company} · {locationLabel(target.location) ?? t("common.locationNotStated")}</small></div>
        <span className="target-created">{t("targets.added", { date: formatDay(target.created_at, lang) })}</span>
      </header>
      <section>
        <div className="target-progress">
          <strong>{progress}%</strong>
          <span>{t("targets.preparationSteps", { completed })}</span>
          <div className="progress"><i style={{ width: `${progress}%` }} /></div>
        </div>
        <label>{t("targets.applicationStage")}<select value={target.stage} disabled><option value={target.stage}>{stage}</option></select></label>
        {target.stage_note && <p className="target-stage-note">{target.stage_note}</p>}
        {target.url && <a href={target.url} target="_blank" rel="noreferrer">{t("targets.openApplication")}</a>}
      </section>
      <section className="steps">
        <ProgressStep done title={t("targets.step.matched")} detail={t("targets.step.matchedDetail")} action={t("targets.review")} onClick={() => go("jobs")} />
        <ProgressStep done={target.rewrite_status !== "none"} title={t("targets.step.tailored")} detail={rewriteDetail} action={t("targets.continue")} onClick={() => navigate(`${ROUTES.rewrite.path}?job=${target.job_id}`)} />
        <ProgressStep done={Boolean(target.interview_done_at)} title={t("targets.step.interview")} detail={target.interview_done_at ? t("targets.interviewDone") : t("targets.interviewPending")} action={t("targets.start")} onClick={() => go("interview")} />
        <ProgressStep done={target.stage !== "not_applied"} title={t("targets.step.submitted")} detail={stage} action={t("targets.track")} />
      </section>
    </article>
  );
}
