import { useState } from "react";
import { ProgressStep } from "../components/common/ProgressStep";
import { PageFrame } from "../components/layout/PageFrame";
import { JOBS } from "../mocks/data";
import type { Page } from "../types/domain";

const STAGES = ["Not applied", "Submitted", "Written test", "Interview 1", "Interview 2", "HR interview", "Offer", "Rejected"];

export function TargetsPage({ targetIds, setTargetIds, navigate }: { targetIds: number[]; setTargetIds: (ids: number[]) => void; navigate: (page: Page) => void }) {
  const [stages, setStages] = useState<Record<number, string>>({});
  const selected = JOBS.filter((job) => targetIds.includes(job.id));
  return (
    <PageFrame eyebrow="TARGET JOBS · PREPARATION PROGRESS" title="My target jobs" description="Continue preparation for each saved role and keep its current application stage in one place.">
      <div className="target-summary"><div><strong>{selected.length}</strong><span>target roles</span></div><div><strong>25%</strong><span>average progress</span></div><div><strong>{Object.values(stages).filter((stage) => stage !== "Not applied").length}</strong><span>submitted</span></div></div>
      <div className="target-list">{selected.map((job) => {
        const stage = stages[job.id] || "Not applied";
        return (
          <article className="target" key={job.id}>
            <header><div className="score"><strong>{job.score}</strong><span>MATCH</span></div><div><h2>{job.title}</h2><small>{job.company} · {job.location}</small></div><button className="ghost" onClick={() => setTargetIds(targetIds.filter((id) => id !== job.id))}>Remove</button></header>
            <section><div className="target-progress"><strong>25%</strong><span>Preparation · 1 / 4 steps</span><div className="progress"><i style={{ width: "25%" }} /></div></div><label>Application stage<select value={stage} onChange={(event) => setStages({ ...stages, [job.id]: event.target.value })}>{STAGES.map((item) => <option key={item}>{item}</option>)}</select></label><a href="#apply">Open application link ↗</a></section>
            <section className="steps"><ProgressStep done title="JD parsed & matched" detail="Match evidence is ready" action="Review" onClick={() => navigate("jobs")} /><ProgressStep title="Resume tailored" detail="No saved final draft" action="Continue" onClick={() => navigate("rewrite")} /><ProgressStep title="Mock interview" detail="Practice not completed" action="Start" onClick={() => navigate("interview")} /><ProgressStep done={stage !== "Not applied"} title="Application submitted" detail={stage} action="Update" /></section>
          </article>
        );
      })}</div>
    </PageFrame>
  );
}
