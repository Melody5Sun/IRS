import { useEffect, useMemo, useState } from "react";
import { jobsApi } from "../../api/jobs";
import { profileApi } from "../../api/profile";
import { targetsApi } from "../../api/targets";
import type { JobMatchDetail, RankingJob, RankingResponse, TargetJob, UserProfile } from "../../types/api";
import { filterJobs, PER_PAGE, type JobFilter, type MinimumLevel } from "./recommendation";

// 错误一律保存原始 reason，由页面按当前语言转成文案
type Failure = { reason: unknown };

// 岗位推荐页的全部状态与接口调用：排序、匹配详情、目标岗位增删、筛选分页
export function useRecommendations(setTargetIds: (ids: number[]) => void) {
  const [ranking, setRanking] = useState<RankingResponse | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [targets, setTargets] = useState<TargetJob[]>([]);
  const [details, setDetails] = useState<Record<number, JobMatchDetail>>({});
  const [detailErrors, setDetailErrors] = useState<Record<number, Failure>>({});
  const [detailLoading, setDetailLoading] = useState<number | null>(null);
  const [targetLoading, setTargetLoading] = useState<number | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [targetAction, setTargetAction] = useState<number | null>(null);
  const [removeTarget, setRemoveTarget] = useState<TargetJob | null>(null);
  const [removeChecked, setRemoveChecked] = useState(false);
  const [filter, setFilter] = useState<JobFilter>("all");
  const [minimumLevel, setMinimumLevel] = useState<MinimumLevel>("all");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Failure | null>(null);
  const [actionError, setActionError] = useState<Failure | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([jobsApi.rank(), profileApi.get(), targetsApi.list()])
      .then(([rankingResult, savedProfile, targetList]) => {
        if (!active) return;
        setRanking(rankingResult);
        setProfile(savedProfile);
        setTargets(targetList);
        setTargetIds(targetList.map((target) => target.job_id));
      })
      .catch((reason) => active && setError({ reason }))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [setTargetIds]);

  const filtered = useMemo(() => filterJobs(ranking?.results ?? [], filter, minimumLevel), [filter, minimumLevel, ranking]);

  const pageTotal = Math.max(1, Math.ceil(filtered.length / PER_PAGE));
  const pageJobs = filtered.slice((page - 1) * PER_PAGE, page * PER_PAGE);
  const targetByJob = new Map(targets.map((target) => [target.job_id, target]));
  const internshipCount = ranking?.results.filter((job) => job.employment_type === "internship").length ?? 0;
  const fullTimeCount = ranking?.results.filter((job) => job.employment_type === "full_time").length ?? 0;

  useEffect(() => setPage(1), [filter, minimumLevel]);
  useEffect(() => { if (page > pageTotal) setPage(pageTotal); }, [page, pageTotal]);

  const toggleDetail = async (jobId: number) => {
    setTargetAction(null);
    if (expanded === jobId) { setExpanded(null); return; }
    setExpanded(jobId);
    if (details[jobId] || !profile) return;
    setDetailLoading(jobId);
    setDetailErrors((current) => { const next = { ...current }; delete next[jobId]; return next; });
    try {
      const detail = await jobsApi.getMatchDetail(jobId, profile);
      setDetails((current) => ({ ...current, [jobId]: detail }));
    } catch (reason) {
      setDetailErrors((current) => ({ ...current, [jobId]: { reason } }));
    } finally { setDetailLoading(null); }
  };

  const selectTarget = async (job: RankingJob) => {
    const existing = targetByJob.get(job.job_id);
    if (existing) {
      setExpanded(null);
      setTargetAction(targetAction === job.job_id ? null : job.job_id);
      return;
    }
    setTargetLoading(job.job_id); setActionError(null);
    try {
      const added = await targetsApi.add(job.job_id, job.final_score);
      const next = [added, ...targets.filter((target) => target.job_id !== added.job_id)];
      setTargets(next);
      setTargetIds(next.map((target) => target.job_id));
      setTargetAction(job.job_id);
    } catch (reason) { setActionError({ reason }); }
    finally { setTargetLoading(null); }
  };

  const requestRemove = (target: TargetJob) => { setRemoveTarget(target); setRemoveChecked(false); };
  const cancelRemove = () => { setRemoveTarget(null); setRemoveChecked(false); };

  const confirmRemove = async () => {
    if (!removeTarget || !removeChecked) return;
    setTargetLoading(removeTarget.job_id); setActionError(null);
    try {
      await targetsApi.remove(removeTarget.job_id);
      const next = targets.filter((target) => target.job_id !== removeTarget.job_id);
      setTargets(next);
      setTargetIds(next.map((target) => target.job_id));
      setTargetAction(null); setRemoveTarget(null); setRemoveChecked(false);
    } catch (reason) { setActionError({ reason }); }
    finally { setTargetLoading(null); }
  };

  return {
    ranking, loading, error, actionError,
    filter, setFilter, minimumLevel, setMinimumLevel,
    filtered, pageJobs, page, setPage, pageTotal, internshipCount, fullTimeCount,
    details, detailErrors, detailLoading, expanded, toggleDetail,
    targetByJob, targetLoading, targetAction, setTargetAction, selectTarget,
    removeTarget, removeChecked, setRemoveChecked, requestRemove, cancelRemove, confirmRemove,
  };
}
