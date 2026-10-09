import { useGo } from "../../app/routes";
import { DashboardCard } from "../../components/common/DashboardCard";
import { useI18n } from "../../i18n/LanguageProvider";
import { JOBS } from "../../mocks/data";

// 仪表盘目前仍展示示例数据，尚未接入接口
export function DashboardPage({ targetIds }: { targetIds: number[] }) {
  const { t } = useI18n();
  const go = useGo();
  const selected = JOBS.filter((job) => targetIds.includes(job.id));
  return (
    <>
      <header className="hero">
        <div>
          <div className="eyebrow">{t("dashboard.date")}</div>
          <h1>{t("dashboard.greeting")}</h1>
          <p>{t("dashboard.heroBefore")}<em>{t("dashboard.heroHighlight")}</em>{t("dashboard.heroAfter")}</p>
        </div>
        <div className="hero-stats">
          <div><strong>12</strong><span>{t("dashboard.statMatches")}</span></div>
          <div><strong>6</strong><span>{t("dashboard.statApplications")}</span></div>
        </div>
      </header>
      <div className="dash-grid three">
        <DashboardCard title={t("nav.jobs")} meta={t("dashboard.jobsMeta")} text={t("dashboard.jobsText")} onExplore={() => go("jobs")}>
          <div className="mini-jobs">{JOBS.slice(0, 3).map((job) => <div key={job.id}><strong>{job.score}</strong><span><b>{job.title}</b><small>{job.company} · {job.location}</small></span><em>{job.type}</em></div>)}</div>
        </DashboardCard>
        <DashboardCard title={t("nav.rewrite")} meta={t("dashboard.rewriteMeta")} text={t("dashboard.rewriteText")} onExplore={() => go("rewrite")}>
          <div className="mini-diff">
            <div><small>{t("dashboard.original")}</small><del>Responsible for backend API development using Spring Boot.</del></div>
            <div><small>{t("dashboard.tailored")}</small><ins>Rebuilt payment callbacks with Spring Boot, reducing P99 latency from 820ms to 210ms.</ins></div>
          </div>
          <p className="fine">{t("dashboard.rewriteNote")}</p>
        </DashboardCard>
        <DashboardCard title={t("nav.interview")} meta={t("dashboard.interviewMeta")} text={t("dashboard.interviewText")} onExplore={() => go("interview")}>
          <div className="camera"><span>{t("dashboard.cameraPreview")}</span><small><i /> REC 00:00</small></div>
        </DashboardCard>
      </div>
      <div className="dash-grid two">
        <DashboardCard title={t("nav.targets")} meta={t("dashboard.targetsMeta", { count: selected.length })} text={t("dashboard.targetsText")} onExplore={() => go("targets")}>
          {selected.map((job) => <div className="mini-target" key={job.id}>
            <div><b>{job.title}</b><span>25%</span></div>
            <small>{job.company}</small>
            <div className="progress"><i style={{ width: "25%" }} /></div>
            <p><em>{t("targets.stage.notApplied")}</em><em>{t("dashboard.resumePending")}</em><em>{t("dashboard.interviewPending")}</em></p>
          </div>)}
        </DashboardCard>
        <DashboardCard title={t("dashboard.profileTitle")} meta={t("dashboard.profileMeta")} text={t("dashboard.profileText")} onExplore={() => go("profile")}>
          <table><tbody>
            <tr><td>{t("dashboard.row.roles")}</td><td>Backend Developer</td></tr>
            <tr><td>{t("dashboard.row.industry")}</td><td>Financial Technology</td></tr>
            <tr><td>{t("dashboard.row.workModes")}</td><td>{t("profile.workMode.hybrid")}, {t("profile.workMode.onsite")}</td></tr>
            <tr><td>{t("dashboard.row.status")}</td><td>{t("dashboard.row.statusValue")}</td></tr>
            <tr><td>{t("dashboard.row.notes")}</td><td>{t("dashboard.row.notesValue")}</td></tr>
          </tbody></table>
        </DashboardCard>
      </div>
    </>
  );
}
