import { useEffect, useState } from "react";
import { ApiError } from "../../api";
import { targetsApi } from "../../api/targets";
import { useGo } from "../../app/routes";
import { PageFrame } from "../../components/layout/PageFrame";
import { useI18n, type Translate } from "../../i18n/LanguageProvider";
import { detailOr } from "../../lib/apiError";
import type { TargetJob } from "../../types/api";
import { averageProgress } from "./progress";
import { TargetCard } from "./TargetCard";

function errorMessage(error: unknown, t: Translate) {
  return error instanceof ApiError ? detailOr(error, t("targets.loadError")) : t("targets.loadError");
}

export function TargetsPage() {
  const { t } = useI18n();
  const go = useGo();
  const [targets, setTargets] = useState<TargetJob[]>([]);
  const [loading, setLoading] = useState(true);
  // 保存原始错误而不是文案，切换语言时错误提示也会跟着切换
  const [failure, setFailure] = useState<{ reason: unknown } | null>(null);

  useEffect(() => {
    let active = true;
    targetsApi.list()
      .then((items) => { if (active) setTargets(items); })
      .catch((reason) => { if (active) setFailure({ reason }); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const submittedCount = targets.filter((target) => target.stage !== "not_applied").length;

  return (
    <PageFrame eyebrow={t("targets.eyebrow")} title={t("targets.title")} description={t("targets.description")}>
      {failure && <div className="form-message error">{errorMessage(failure.reason, t)}</div>}
      {loading ? <div className="interview-state"><h2>{t("targets.loading")}</h2></div> : <>
        <div className="target-summary">
          <div><strong>{targets.length}</strong><span>{t("targets.summaryRoles")}</span></div>
          <div><strong>{averageProgress(targets)}%</strong><span>{t("targets.summaryProgress")}</span></div>
          <div><strong>{submittedCount}</strong><span>{t("targets.summarySubmitted")}</span></div>
        </div>
        {!targets.length ? (
          <div className="interview-state">
            <h2>{t("targets.emptyTitle")}</h2>
            <p>{t("targets.emptyText")}</p>
            <button className="primary" onClick={() => go("jobs")}>{t("targets.emptyAction")}</button>
          </div>
        ) : <div className="target-list">{targets.map((target) => <TargetCard key={target.job_id} target={target} onChange={(updated) => setTargets((current) => current.map((item) => item.job_id === updated.job_id ? updated : item))} />)}</div>}
      </>}
    </PageFrame>
  );
}
