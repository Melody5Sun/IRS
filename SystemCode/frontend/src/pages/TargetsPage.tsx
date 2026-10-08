import { useEffect, useMemo, useState } from "react";
import { ApiError } from "../api";
import { targetsApi } from "../api/targets";
import { ProgressStep } from "../components/common/ProgressStep";
import { PageFrame } from "../components/layout/PageFrame";
import type { TargetJob } from "../types/api";
import type { Page } from "../types/domain";

const STAGE_LABELS: Record<string, string> = {
  not_applied: "Not applied",
  submitted: "Submitted",
  written_test: "Written test",
  interview_1: "Interview 1",
  interview_2: "Interview 2",
  hr_interview: "HR interview",
  offer: "Offer",
  rejected: "Rejected",
};

function locationLabel(location: unknown) {
  if (!location) return "Location not stated";
  if (typeof location === "string") return location;
  if (typeof location === "object") {
    const value = location as { city?: unknown; country?: unknown };
    const parts = [value.city, value.country].filter((part): part is string => typeof part === "string" && Boolean(part.trim()));
    return [...new Set(parts.map((part) => part.trim()))].join(", ") || "Location not stated";
  }
  return "Location not stated";
}

function completedSteps(target: TargetJob) {
  return 1
    + (target.rewrite_status !== "none" ? 1 : 0)
    + (target.interview_done_at ? 1 : 0)
    + (target.stage !== "not_applied" ? 1 : 0);
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError && typeof error.body.detail === "string") return error.body.detail;
  return "Unable to load target jobs. Check that the API server is running.";
}

export function TargetsPage({ navigate }: { navigate: (page: Page) => void }) {
  const [targets, setTargets] = useState<TargetJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    targetsApi.list()
      .then((items) => { if (active) setTargets(items); })
      .catch((reason) => { if (active) setError(errorMessage(reason)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const averageProgress = useMemo(() => {
    if (!targets.length) return 0;
    return Math.round(targets.reduce((total, target) => total + completedSteps(target) * 25, 0) / targets.length);
  }, [targets]);
  const submittedCount = targets.filter((target) => target.stage !== "not_applied").length;

  return (
    <PageFrame eyebrow="TARGET JOBS · PREPARATION PROGRESS" title="My target jobs" description="Continue preparation for each saved role and keep its current application stage in one place.">
      {error && <div className="form-message error">{error}</div>}
      {loading ? <div className="interview-state"><h2>Loading target jobs...</h2></div> : <>
        <div className="target-summary"><div><strong>{targets.length}</strong><span>target roles</span></div><div><strong>{averageProgress}%</strong><span>average progress</span></div><div><strong>{submittedCount}</strong><span>submitted</span></div></div>
        {!targets.length ? <div className="interview-state"><h2>No target jobs yet</h2><p>Add a role from Job recommendations to track preparation here.</p><button className="primary" onClick={() => navigate("jobs")}>Explore recommended jobs →</button></div> : <div className="target-list">{targets.map((target) => {
          const completed = completedSteps(target);
          const progress = completed * 25;
          const stage = STAGE_LABELS[target.stage] ?? target.stage;
          return (
            <article className="target" key={target.job_id}>
              <header><div className="score"><strong>{target.match_score == null ? "—" : Math.round(target.match_score)}</strong><span>MATCH</span></div><div><h2>{target.title}</h2><small>{target.company} · {locationLabel(target.location)}</small></div><span className="target-created">Added {new Intl.DateTimeFormat("en-SG", { day: "numeric", month: "short", year: "numeric" }).format(new Date(target.created_at))}</span></header>
              <section><div className="target-progress"><strong>{progress}%</strong><span>Preparation · {completed} / 4 steps</span><div className="progress"><i style={{ width: `${progress}%` }} /></div></div><label>Application stage<select value={target.stage} disabled><option value={target.stage}>{stage}</option></select></label>{target.stage_note && <p className="target-stage-note">{target.stage_note}</p>}{target.url && <a href={target.url} target="_blank" rel="noreferrer">Open application link ↗</a>}</section>
              <section className="steps"><ProgressStep done title="JD parsed & matched" detail="Match evidence is ready" action="Review" onClick={() => navigate("jobs")} /><ProgressStep done={target.rewrite_status !== "none"} title="Resume tailored" detail={target.rewrite_status === "stale" ? "Saved draft uses an older profile" : target.rewrite_status === "saved" ? "Tailored draft saved" : "No saved final draft"} action="Continue" onClick={() => navigate("rewrite")} /><ProgressStep done={Boolean(target.interview_done_at)} title="Mock interview" detail={target.interview_done_at ? "Practice completed" : "Practice not completed"} action="Start" onClick={() => navigate("interview")} /><ProgressStep done={target.stage !== "not_applied"} title="Application submitted" detail={stage} action="Track" /></section>
            </article>
          );
        })}</div>}
      </>}
    </PageFrame>
  );
}
