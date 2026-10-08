import { useEffect, useMemo, useState } from "react";
import { ApiError } from "../api";
import { jobsApi } from "../api/jobs";
import { profileApi } from "../api/profile";
import { targetsApi } from "../api/targets";
import type { JobMatchDetail, RankingJob, RankingResponse, TargetJob, UserProfile } from "../types/api";
import type { Page } from "../types/domain";

type JobFilter = "all" | "internship" | "full_time";
type RecommendationLevel = "all" | "limited" | "potential" | "recommended" | "highly";

const PER_PAGE = 10;

const RECOMMENDATION_LEVELS = {
  limited: { label: "Limited Match", rank: 0 },
  potential: { label: "Potential Match", rank: 1 },
  recommended: { label: "Recommended", rank: 2 },
  highly: { label: "Highly Recommended", rank: 3 },
} as const;

function recommendationLevel(score: number) {
  if (score >= 50) return { key: "highly" as const, ...RECOMMENDATION_LEVELS.highly };
  if (score >= 30) return { key: "recommended" as const, ...RECOMMENDATION_LEVELS.recommended };
  if (score >= 15) return { key: "potential" as const, ...RECOMMENDATION_LEVELS.potential };
  return { key: "limited" as const, ...RECOMMENDATION_LEVELS.limited };
}

function locationLabel(location: RankingJob["location"]) {
  if (!location) return "Location not stated";
  const values = [location.city, location.country].filter(Boolean) as string[];
  return [...new Set(values.map((value) => value.trim()))].join(", ") || "Location not stated";
}

function employmentLabel(value: string) {
  return value === "full_time" ? "Full-time" : value === "part_time" ? "Part-time" : value === "internship" ? "Internship" : value.split("_").join(" ");
}

function sourceLabel(value: string) {
  const labels: Record<string, string> = {
    skills: "Resume skills", experience: "Experience", project: "Project",
    research: "Research", career_intent: "Career intent",
  };
  return labels[value] ?? value.split("_").join(" ");
}

function matchTypeLabel(value: string) {
  return value.split("_").join(" ").replace(/\b\w/g, (letter: string) => letter.toUpperCase());
}

function formatDate(value: string | null) {
  if (!value) return "date not stated";
  return new Intl.DateTimeFormat("en-SG", { day: "numeric", month: "short", year: "numeric" }).format(new Date(value));
}

function errorMessage(error: unknown, area: "ranking" | "detail" | "target") {
  if (!(error instanceof ApiError)) return "Unable to connect to the backend. Check that the API server is running.";
  if (error.status === 409 && area === "ranking") return "Save your resume profile and career intent before generating job recommendations.";
  if (error.status === 409 && area === "detail") return "Match details are not available because this job has not been analysed yet.";
  if (error.status === 404 && area === "detail") return "This job is no longer available.";
  if (error.status === 404 && area === "target") return "This target job could not be found.";
  return typeof error.body.detail === "string" ? error.body.detail : "The request could not be completed.";
}

export function JobsPage({ setTargetIds, navigate }: { targetIds: number[]; setTargetIds: (ids: number[]) => void; navigate: (page: Page) => void }) {
  const [ranking, setRanking] = useState<RankingResponse | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [targets, setTargets] = useState<TargetJob[]>([]);
  const [details, setDetails] = useState<Record<number, JobMatchDetail>>({});
  const [detailErrors, setDetailErrors] = useState<Record<number, string>>({});
  const [detailLoading, setDetailLoading] = useState<number | null>(null);
  const [targetLoading, setTargetLoading] = useState<number | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [targetAction, setTargetAction] = useState<number | null>(null);
  const [removeTarget, setRemoveTarget] = useState<TargetJob | null>(null);
  const [removeChecked, setRemoveChecked] = useState(false);
  const [filter, setFilter] = useState<JobFilter>("all");
  const [minimumLevel, setMinimumLevel] = useState<RecommendationLevel>("all");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

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
      .catch((reason) => active && setError(errorMessage(reason, "ranking")))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [setTargetIds]);

  const filtered = useMemo(() => (ranking?.results ?? []).filter((job) => {
    const matchesType = filter === "all" || job.employment_type === filter;
    const matchesLevel = minimumLevel === "all" || recommendationLevel(job.final_score).rank >= RECOMMENDATION_LEVELS[minimumLevel].rank;
    return matchesType && matchesLevel;
  }), [filter, minimumLevel, ranking]);

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
      setDetailErrors((current) => ({ ...current, [jobId]: errorMessage(reason, "detail") }));
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
    } catch (reason) { setActionError(errorMessage(reason, "target")); }
    finally { setTargetLoading(null); }
  };

  const confirmRemove = async () => {
    if (!removeTarget || !removeChecked) return;
    setTargetLoading(removeTarget.job_id); setActionError(null);
    try {
      await targetsApi.remove(removeTarget.job_id);
      const next = targets.filter((target) => target.job_id !== removeTarget.job_id);
      setTargets(next);
      setTargetIds(next.map((target) => target.job_id));
      setTargetAction(null); setRemoveTarget(null); setRemoveChecked(false);
    } catch (reason) { setActionError(errorMessage(reason, "target")); }
    finally { setTargetLoading(null); }
  };

  const pageNumbers = Array.from({ length: pageTotal }, (_, index) => index + 1);

  return <div className="recommendations-page">
    <header className="recommendations-header">
      <div><div className="eyebrow">STEP 02 · CLEAN JD · RANK & EXPLAIN</div><h1>Job recommendations</h1></div>
      <p>Your target roles and industries are applied as filters before eligible jobs are ranked. Open a role to see the resume evidence behind each match and the gaps to strengthen.</p>
    </header>

    {loading && <div className="recommendations-state"><h2>Ranking eligible roles...</h2><p>Applying your saved profile, constraints and matching evidence.</p></div>}
    {!loading && error && <div className="recommendations-state"><h2>Recommendations are not available</h2><p>{error}</p><button className="primary" onClick={() => navigate("profile")}>Complete profile →</button></div>}

    {!loading && !error && ranking && <>
      <div className="job-tools recommendations-tools">
        <div className="seg" aria-label="Employment type filter">
          <button className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>All {ranking.returned_count}</button>
          <button className={filter === "internship" ? "active" : ""} onClick={() => setFilter("internship")}>Internships {internshipCount}</button>
          <button className={filter === "full_time" ? "active" : ""} onClick={() => setFilter("full_time")}>Full-time {fullTimeCount}</button>
        </div>
        <label className="recommendation-level-filter"><span>Minimum recommendation</span><select value={minimumLevel} onChange={(event) => setMinimumLevel(event.target.value as RecommendationLevel)}><option value="all">All levels</option><option value="potential">Potential Match</option><option value="recommended">Recommended</option><option value="highly">Highly Recommended</option></select></label>
        <span>{filtered.length} eligible roles · highest match first</span>
      </div>

      {actionError && <div className="job-action-error" role="alert">{actionError}</div>}

      <div className="recommendations-pane">
        {pageJobs.map((job) => {
          const detail = details[job.job_id];
          const target = targetByJob.get(job.job_id);
          const open = expanded === job.job_id;
          const level = recommendationLevel(job.final_score);
          return <article className="job recommendation-job" key={job.job_id}>
            <div className={`recommendation-level ${level.key}`}><strong>{level.label}</strong><span>RECOMMENDATION</span></div>
            <div className="job-main">
              <h2>{job.title}</h2>
              <small>{job.company} · {locationLabel(job.location)} · {employmentLabel(job.employment_type)}</small>
              <p>{detail?.recommendation.summary ?? "Open match details to review the evidence behind this ranking and the areas to strengthen."}</p>
              {detail && <div className="tags">{detail.job.required_skills.map((skill) => <em key={skill}>{skill}</em>)}{detail.job.preferred_skills.map((skill) => <em className="preferred" key={skill}>{skill} · preferred</em>)}</div>}
            </div>
            <div className="job-actions">
              <button className="secondary" disabled={detailLoading === job.job_id} onClick={() => toggleDetail(job.job_id)}>{detailLoading === job.job_id ? "Loading match..." : open ? "Hide details" : "View match"}</button>
              <button className="primary" disabled={targetLoading === job.job_id} onClick={() => selectTarget(job)}>{targetLoading === job.job_id ? "Updating..." : target ? "Target added · Manage" : "Set as target →"}</button>
            </div>

            {targetAction === job.job_id && target && <div className="target-action-panel"><p>This role is in your target list. View its preparation progress or remove it from your targets.</p><button className="primary" onClick={() => navigate("targets")}>View preparation progress →</button><button className="secondary" onClick={() => { setRemoveTarget(target); setRemoveChecked(false); }}>Remove target</button><button className="ghost" onClick={() => setTargetAction(null)}>Cancel</button></div>}

            {open && <div className="match recommendation-match">
              {detailLoading === job.job_id && <div className="match-loading">Loading evidence and skill gaps...</div>}
              {detailErrors[job.job_id] && <div className="match-loading error">{detailErrors[job.job_id]}</div>}
              {detail && <>
                <section><h3>Matching evidence</h3>{detail.recommendation.evidence.length ? detail.recommendation.evidence.map((evidence, index) => <div className="evidence-row" key={`${evidence.requirement}-${index}`}><strong>Job requirement · {evidence.requirement}</strong><p>Resume evidence · {evidence.candidate_evidence}</p><small>{sourceLabel(evidence.evidence_source)} · {matchTypeLabel(evidence.match_type)} · {Math.round(evidence.similarity * 100)}% confidence</small></div>) : <p className="empty-detail">No direct resume evidence was returned for this role.</p>}</section>
                <section><h3>Gaps and improvement</h3>{detail.gaps.length ? detail.gaps.map((gap, index) => <div className="gap-row" key={`${gap.name}-${index}`}><div><em>{gap.gap_type.split("_").join(" ")}</em><strong>{gap.name}</strong></div><p>{gap.suggestion || gap.reason}</p></div>) : <p className="empty-detail">No material gaps were identified.</p>}<div className="improvement-note"><strong>Recommended next step</strong><p>{detail.improvement_plan.summary}</p>{detail.improvement_plan.next_action && <p>{detail.improvement_plan.next_action}</p>}</div><small className="job-source-note">JD collected {formatDate(detail.job.collected_at)} · {detail.job.responsibilities.length} responsibilities · {detail.job.required_skills.length + detail.job.preferred_skills.length} skill requirements</small></section>
                {detail.job.url && <footer><a className="secondary job-link" href={detail.job.url} target="_blank" rel="noreferrer">Open application ↗</a></footer>}
              </>}
            </div>}
          </article>;
        })}

        {pageJobs.length === 0 && <div className="recommendations-empty"><h2>No roles meet this match threshold</h2><p>Lower the minimum match score or choose a different employment type.</p></div>}
      </div>

      <div className="recommendations-pagination">
        <span>Page {page} / {pageTotal} · {PER_PAGE} per page · {filtered.length} roles</span>
        <div><button className="secondary" disabled={page === 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>‹ Previous</button>{pageNumbers.map((number) => number === page ? <span className="current-page" key={number}>{number}</span> : <button className="ghost page-number" key={number} onClick={() => setPage(number)}>{number}</button>)}<button className="secondary" disabled={page === pageTotal} onClick={() => setPage((current) => Math.min(pageTotal, current + 1))}>Next ›</button></div>
      </div>
    </>}

    {removeTarget && <div className="dialog-backdrop"><div className="profile-dialog remove-target-dialog" role="dialog" aria-modal="true" aria-labelledby="remove-target-title"><h2 id="remove-target-title">Remove target role?</h2><h3>{removeTarget.title}</h3><small>{removeTarget.company}</small><p>Removing this target also deletes its saved resume rewrite and preparation records. This cannot be undone. The role will remain in recommendations.</p><label className="remove-confirm"><input type="checkbox" checked={removeChecked} onChange={(event) => setRemoveChecked(event.target.checked)} /><span>I understand and want to remove this target and its preparation records.</span></label><div className="dialog-actions"><button className="secondary" onClick={() => { setRemoveTarget(null); setRemoveChecked(false); }}>Cancel</button><button className="primary" disabled={!removeChecked || targetLoading === removeTarget.job_id} onClick={confirmRemove}>{targetLoading === removeTarget.job_id ? "Removing..." : "Confirm removal"}</button></div></div></div>}
  </div>;
}
