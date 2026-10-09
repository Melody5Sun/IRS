import { useEffect, useState } from "react";
import { ApiError, jobsApi, profileApi, targetsApi } from "../../api";
import { useGo } from "../../app/routes";
import { DashboardCard } from "../../components/common/DashboardCard";
import { useI18n, type Translate } from "../../i18n/LanguageProvider";
import { detailOr } from "../../lib/apiError";
import { formatDay, localeOf, locationLabel } from "../../lib/format";
import type { RankingResponse, SavedProfile, TargetJob } from "../../types/api";
import { employmentLabel, recommendationLevel } from "../jobs/recommendation";
import { WORK_MODE_OPTIONS } from "../profile/constants";
import { averageProgress, completedSteps, stageLabel } from "../targets/progress";

type DashboardData = {
  profile: SavedProfile | null;
  ranking: RankingResponse | null;
  targets: TargetJob[];
  // 保存原始错误，切换语言时文案跟着变
  failure: unknown;
};

// 没有画像时 /profile 返回 404、/ranking 返回 409，属于正常的空状态，不算错误
const missingProfile = (reason: unknown) => reason instanceof ApiError && (reason.status === 404 || reason.status === 409);

function errorMessage(reason: unknown, t: Translate) {
  return reason instanceof ApiError ? detailOr(reason, t("common.requestFailed")) : t("common.connectionError");
}

export function DashboardPage() {
  const { lang, t } = useI18n();
  const go = useGo();
  const [data, setData] = useState<DashboardData | null>(null);

  useEffect(() => {
    let active = true;
    // 三个接口互不依赖，任何一个失败都不影响其他卡片
    Promise.allSettled([profileApi.get(), jobsApi.rank(), targetsApi.list()]).then(([profile, ranking, targets]) => {
      if (!active) return;
      const failure = [profile, ranking, targets].find((result) => result.status === "rejected" && !missingProfile(result.reason));
      setData({
        profile: profile.status === "fulfilled" ? profile.value : null,
        ranking: ranking.status === "fulfilled" ? ranking.value : null,
        targets: targets.status === "fulfilled" ? targets.value : [],
        failure: failure?.status === "rejected" ? failure.reason : null,
      });
    });
    return () => { active = false; };
  }, []);

  const profile = data?.profile ?? null;
  const ranking = data?.ranking ?? null;
  const targets = data?.targets ?? [];
  const results = ranking?.results ?? [];
  const top = results[0];
  const strongCount = results.filter((job) => recommendationLevel(job.final_score) === "highly").length;
  const submittedCount = targets.filter((target) => target.stage !== "not_applied").length;
  const writtenTestCount = targets.filter((target) => target.stage === "written_test").length;
  const rewriteCount = targets.filter((target) => target.rewrite_status !== "none").length;
  const interviewCount = targets.filter((target) => target.interview_done_at).length;
  const name = profile?.resume.name?.trim();
  const constraints = profile?.constraints;
  const workModes = constraints?.work_modes.map((mode) => {
    const option = WORK_MODE_OPTIONS.find(([value]) => value === mode);
    return option ? t(option[1]) : mode;
  });
  const shownTargets = targets.slice(0, 3);
  const noTargets = <p className="fine">{t("dashboard.targetsEmpty")}</p>;

  let hero;
  if (!data) hero = t("dashboard.loading");
  else if (top) hero = <>{t("dashboard.heroBefore", { count: results.length, strong: strongCount })}<em>{top.title} · {top.company}</em>{t("dashboard.heroAfter")}</>;
  else if (!profile) hero = t("dashboard.heroNoProfile");
  else hero = t("dashboard.heroNoMatches");

  return (
    <>
      <header className="hero">
        <div>
          <div className="eyebrow">{new Intl.DateTimeFormat(localeOf(lang), { dateStyle: "full" }).format(new Date())}</div>
          <h1>{name ? t("dashboard.greeting", { name }) : t("dashboard.greetingAnonymous")}</h1>
          <p>{hero}</p>
        </div>
        <div className="hero-stats">
          <div><strong>{ranking ? results.length : "—"}</strong><span>{t("dashboard.statMatches")}</span></div>
          <div><strong>{submittedCount}</strong><span>{t("dashboard.statApplications", { count: writtenTestCount })}</span></div>
        </div>
      </header>
      {data?.failure != null && <div className="form-message error">{errorMessage(data.failure, t)}</div>}
      <div className="dash-grid three">
        <DashboardCard title={t("nav.jobs")} meta={ranking ? t("dashboard.jobsMeta", { count: results.length, strong: strongCount }) : "—"} text={t("dashboard.jobsText")} onExplore={() => go(profile ? "jobs" : "profile")}>
          {results.length ? <div className="mini-jobs">{results.slice(0, 3).map((job) => <div key={job.job_id}>
            <strong>{Math.round(job.final_score)}</strong>
            <span><b>{job.title}</b><small>{job.company} · {locationLabel(job.location) ?? t("common.locationNotStated")}</small></span>
            <em>{employmentLabel(job.employment_type, t)}</em>
          </div>)}</div> : <p className="fine">{profile ? t("dashboard.heroNoMatches") : t("dashboard.heroNoProfile")}</p>}
        </DashboardCard>
        <DashboardCard title={t("nav.rewrite")} meta={t("dashboard.rewriteMeta", { done: rewriteCount, total: targets.length })} text={t("dashboard.rewriteText")} onExplore={() => go("rewrite")}>
          {shownTargets.length ? <div className="mini-jobs">{shownTargets.map((target) => <div key={target.job_id}>
            <span><b>{target.title}</b><small>{target.company}</small></span>
            <em>{target.rewrite_status === "stale" ? t("targets.rewriteStale") : target.rewrite_status === "saved" ? t("targets.rewriteSaved") : t("dashboard.resumePending")}</em>
          </div>)}</div> : noTargets}
        </DashboardCard>
        <DashboardCard title={t("nav.interview")} meta={t("dashboard.interviewMeta", { done: interviewCount, total: targets.length })} text={t("dashboard.interviewText")} onExplore={() => go("interview")}>
          {shownTargets.length ? <div className="mini-jobs">{shownTargets.map((target) => <div key={target.job_id}>
            <span><b>{target.title}</b><small>{target.company}</small></span>
            <em>{target.interview_done_at ? t("targets.interviewDone") : t("dashboard.interviewPending")}</em>
          </div>)}</div> : noTargets}
        </DashboardCard>
      </div>
      <div className="dash-grid two">
        <DashboardCard title={t("nav.targets")} meta={t("dashboard.targetsMeta", { count: targets.length, average: averageProgress(targets) })} text={t("dashboard.targetsText")} onExplore={() => go("targets")}>
          {shownTargets.length ? shownTargets.map((target) => {
            const progress = completedSteps(target) * 25;
            return <div className="mini-target" key={target.job_id}>
              <div><b>{target.title}</b><span>{progress}%</span></div>
              <small>{target.company}</small>
              <div className="progress"><i style={{ width: `${progress}%` }} /></div>
              <p>
                <em>{stageLabel(target.stage, t)}</em>
                <em>{target.rewrite_status === "none" ? t("dashboard.resumePending") : t("targets.rewriteSaved")}</em>
                <em>{target.interview_done_at ? t("targets.interviewDone") : t("dashboard.interviewPending")}</em>
              </p>
            </div>;
          }) : noTargets}
        </DashboardCard>
        <DashboardCard title={t("dashboard.profileTitle")} meta={profile ? t("dashboard.profileMeta", { date: formatDay(profile.updated_at, lang) }) : "—"} text={t("dashboard.profileText")} onExplore={() => go("profile")}>
          {constraints ? <table><tbody>
            <tr><td>{t("dashboard.row.roles")}</td><td>{constraints.target_roles.join(", ") || "—"}</td></tr>
            <tr><td>{t("dashboard.row.industry")}</td><td>{constraints.target_industries.join(", ") || "—"}</td></tr>
            <tr><td>{t("dashboard.row.workModes")}</td><td>{workModes?.join(", ") || "—"}</td></tr>
            <tr><td>{t("dashboard.row.notes")}</td><td>{constraints.notes || "—"}</td></tr>
          </tbody></table> : <p className="fine">{data ? t("dashboard.heroNoProfile") : t("dashboard.loading")}</p>}
        </DashboardCard>
      </div>
    </>
  );
}
