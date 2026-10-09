import { useGo } from "../../app/routes";
import { useI18n } from "../../i18n/LanguageProvider";
import { JobCard } from "./JobCard";
import { JobFilters } from "./JobFilters";
import { jobsErrorMessage } from "./messages";
import { Pagination } from "./Pagination";
import { RemoveTargetDialog } from "./RemoveTargetDialog";
import { useRecommendations } from "./useRecommendations";

export function JobsPage() {
  const { t } = useI18n();
  const go = useGo();
  const state = useRecommendations();
  const { ranking, loading, error, removeTarget } = state;

  return <div className="recommendations-page">
    <header className="recommendations-header">
      <div><div className="eyebrow">{t("jobs.eyebrow")}</div><h1>{t("jobs.title")}</h1></div>
      <p>{t("jobs.description")}</p>
    </header>

    {loading && <div className="recommendations-state"><h2>{t("jobs.loadingTitle")}</h2><p>{t("jobs.loadingText")}</p></div>}
    {!loading && error && <div className="recommendations-state">
      <h2>{t("jobs.unavailable")}</h2>
      <p>{jobsErrorMessage(error.reason, "ranking", t)}</p>
      <button className="primary" onClick={() => go("profile")}>{t("jobs.completeProfile")}</button>
    </div>}

    {!loading && !error && ranking && <>
      <JobFilters
        filter={state.filter}
        onFilter={state.setFilter}
        minimumLevel={state.minimumLevel}
        onMinimumLevel={state.setMinimumLevel}
        counts={{ all: ranking.returned_count, internship: state.internshipCount, full_time: state.fullTimeCount }}
        filteredCount={state.filtered.length}
      />

      {state.actionError && <div className="job-action-error" role="alert">{jobsErrorMessage(state.actionError.reason, "target", t)}</div>}

      <div className="recommendations-pane">
        {state.pageJobs.map((job) => {
          const detailError = state.detailErrors[job.job_id];
          return <JobCard
            key={job.job_id}
            job={job}
            target={state.targetByJob.get(job.job_id)}
            detail={state.details[job.job_id]}
            detailError={detailError && jobsErrorMessage(detailError.reason, "detail", t)}
            open={state.expanded === job.job_id}
            loadingDetail={state.detailLoading === job.job_id}
            updatingTarget={state.targetLoading === job.job_id}
            showTargetPanel={state.targetAction === job.job_id}
            onToggleDetail={() => state.toggleDetail(job.job_id)}
            onSelectTarget={() => state.selectTarget(job)}
            onCloseTargetPanel={() => state.setTargetAction(null)}
            onRequestRemove={state.requestRemove}
          />;
        })}

        {state.pageJobs.length === 0 && <div className="recommendations-empty"><h2>{t("jobs.emptyTitle")}</h2><p>{t("jobs.emptyText")}</p></div>}
      </div>

      <Pagination page={state.page} pageTotal={state.pageTotal} total={state.filtered.length} onChange={state.setPage} />
    </>}

    {removeTarget && <RemoveTargetDialog
      target={removeTarget}
      checked={state.removeChecked}
      onCheckedChange={state.setRemoveChecked}
      busy={state.targetLoading === removeTarget.job_id}
      onCancel={state.cancelRemove}
      onConfirm={state.confirmRemove}
    />}
  </div>;
}
