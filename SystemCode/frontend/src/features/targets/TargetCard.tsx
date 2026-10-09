import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../../api";
import { targetsApi } from "../../api/targets";
import { ROUTES, useGo } from "../../app/routes";
import { ProgressStep } from "../../components/common/ProgressStep";
import { Select } from "../../components/common/Select";
import { useI18n } from "../../i18n/LanguageProvider";
import { detailOr } from "../../lib/apiError";
import { formatDay, locationLabel } from "../../lib/format";
import type { TargetJob } from "../../types/api";
import { APPLIED_STAGES, completedSteps, progressLabel, stageLabel } from "./progress";

export function TargetCard({ target, onChange }: { target: TargetJob; onChange: (target: TargetJob) => void }) {
  const { lang, t } = useI18n();
  const go = useGo();
  const navigate = useNavigate();
  const [note, setNote] = useState(target.stage_note ?? "");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<{ reason: unknown } | null>(null);
  const completed = completedSteps(target);
  const progress = completed * 25;
  const applied = target.stage !== "not_applied";
  const rewriteDetail = target.rewrite_status === "stale" ? t("targets.rewriteStale") : target.rewrite_status === "saved" ? t("targets.rewriteSaved") : t("targets.rewriteNone");

  // 后端撤销投递时会清空备注，以服务端返回的为准
  useEffect(() => setNote(target.stage_note ?? ""), [target.stage_note]);

  const patch = async (updates: { stage?: string; stage_note?: string }) => {
    if (busy) return;
    setBusy(true); setFailure(null);
    try { onChange(await targetsApi.update(target.job_id, updates)); }
    catch (reason) { setFailure({ reason }); }
    finally { setBusy(false); }
  };

  const saveNote = () => { if (note.trim() !== (target.stage_note ?? "")) void patch({ stage_note: note }); };

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
        {target.url && <a href={target.url} target="_blank" rel="noreferrer">{t("targets.openApplication")}</a>}
      </section>
      <section className="steps">
        <ProgressStep done title={t("targets.step.matched")} detail={t("targets.step.matchedDetail")} action={t("targets.review")} onClick={() => go("jobs")} />
        <ProgressStep done={target.rewrite_status !== "none"} title={t("targets.step.tailored")} detail={rewriteDetail} action={t("targets.continue")} onClick={() => navigate(`${ROUTES.rewrite.path}?job=${target.job_id}`)} />
        <ProgressStep done={Boolean(target.interview_done_at)} title={t("targets.step.interview")} detail={target.interview_done_at ? t("targets.interviewDone") : t("targets.interviewPending")} action={t("targets.start")} onClick={() => go("interview")} />
        <ProgressStep done={applied} title={t("targets.step.submitted")} detail={applied ? progressLabel(target, t) : t("targets.submitHint")}
          action={applied ? t("targets.unmarkSubmitted") : t("targets.markSubmitted")} onClick={() => patch({ stage: applied ? "not_applied" : "submitted" })} />
        {/* 投递进度紧跟在「已投递」一步下面：先标记已提交，再就地选阶段或自填 */}
        <div className="target-stage">
          <label>{t("targets.applicationStage")}
            <Select value={target.stage} disabled={!applied || busy} aria-label={t("targets.applicationStage")} onChange={(stage) => patch({ stage })}
              options={(applied ? APPLIED_STAGES : ["not_applied"]).map((stage) => ({ value: stage, label: stageLabel(stage, t) }))} />
          </label>
          <label>{t("targets.stageNote")}
            <input value={note} disabled={!applied || busy} placeholder={t("targets.stageNotePlaceholder")} onChange={(event) => setNote(event.target.value)} onBlur={saveNote} onKeyDown={(event) => { if (event.key === "Enter") saveNote(); }} />
          </label>
          <p className="target-stage-note">{applied ? t("targets.stageHint") : t("targets.stageLocked")}</p>
          {failure && <div className="form-message error">{failure.reason instanceof ApiError ? detailOr(failure.reason, t("targets.updateError")) : t("targets.updateError")}</div>}
        </div>
      </section>
    </article>
  );
}
