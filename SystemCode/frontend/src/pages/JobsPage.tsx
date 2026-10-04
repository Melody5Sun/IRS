import { useState } from "react";
import { PageFrame } from "../components/layout/PageFrame";
import { JOBS } from "../mocks/data";
import type { Page } from "../types/domain";

export function JobsPage({ targetIds, setTargetIds, navigate }: { targetIds: number[]; setTargetIds: (ids: number[]) => void; navigate: (page: Page) => void }) {
  const [minimum, setMinimum] = useState(60);
  const [expanded, setExpanded] = useState<number | null>(92);
  const visibleJobs = JOBS.filter((job) => job.score >= minimum);
  const toggleTarget = (id: number) => setTargetIds(targetIds.includes(id) ? targetIds.filter((value) => value !== id) : [...targetIds, id]);
  return (
    <PageFrame eyebrow="STEP 02 · CLEAN JD · RANK & EXPLAIN" title="Job recommendations" description="Roles are filtered against your constraints, ranked by profile evidence, and explained requirement by requirement.">
      <div className="job-tools">
        <div className="seg"><button className="active">All roles</button><button>Internships</button><button>Full-time</button></div>
        <label>Minimum match <input type="range" min="40" max="90" value={minimum} onChange={(event) => setMinimum(Number(event.target.value))} /><b>{minimum}</b></label>
        <span>{visibleJobs.length} roles · highest match first</span>
      </div>
      <div>{visibleJobs.map((job) => (
        <article className="job" key={job.id}>
          <div className="score"><strong>{job.score}</strong><span>MATCH</span></div>
          <div className="job-main"><h2>{job.title}</h2><small>{job.company} · {job.location} · {job.type}</small><p>{job.summary}</p><div className="tags">{job.skills.map((skill) => <em key={skill}>{skill}</em>)}</div></div>
          <div className="job-actions"><button className="secondary" onClick={() => setExpanded(expanded === job.id ? null : job.id)}>{expanded === job.id ? "Hide details" : "View match"}</button><button className="primary" onClick={() => toggleTarget(job.id)}>{targetIds.includes(job.id) ? "Target added · Manage" : "Set as target →"}</button></div>
          {expanded === job.id && <div className="match"><div><h3>Why this role fits</h3>{job.strengths.map((item) => <p key={item}>+ {item}</p>)}</div><div><h3>What to strengthen</h3>{job.gaps.map((item) => <p key={item}>− {item}</p>)}</div><footer><button className="secondary" onClick={() => navigate("rewrite")}>Tailor resume</button><button className="secondary" onClick={() => navigate("interview")}>Practise interview</button></footer></div>}
        </article>
      ))}</div>
    </PageFrame>
  );
}
