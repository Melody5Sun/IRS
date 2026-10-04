import { DashboardCard } from "../components/common/DashboardCard";
import { JOBS } from "../mocks/data";
import type { Page } from "../types/domain";

export function DashboardPage({ navigate, targetIds }: { navigate: (page: Page) => void; targetIds: number[] }) {
  const selected = JOBS.filter((job) => targetIds.includes(job.id));
  return (
    <>
      <header className="hero">
        <div>
          <div className="eyebrow">MONDAY · 7 SEPTEMBER 2026</div>
          <h1>Hello, Alex</h1>
          <p>12 new roles were matched this week, including 4 strong matches. Start with <em>Lumen Pay's Backend Engineer Internship</em>, where your current evidence aligns most closely.</p>
        </div>
        <div className="hero-stats"><div><strong>12</strong><span>new matches</span></div><div><strong>6</strong><span>applications · 2 tests</span></div></div>
      </header>
      <div className="dash-grid three">
        <DashboardCard title="Job recommendations" meta="12 roles · 4 strong matches" text="Review ranked roles and inspect the evidence behind each recommendation." onExplore={() => navigate("jobs")}>
          <div className="mini-jobs">{JOBS.slice(0, 3).map((job) => <div key={job.id}><strong>{job.score}</strong><span><b>{job.title}</b><small>{job.company} · {job.location}</small></span><em>{job.type}</em></div>)}</div>
        </DashboardCard>
        <DashboardCard title="Resume tailoring" meta="5 blocks · 3 need input" text="Review original and tailored content side by side before saving a final draft." onExplore={() => navigate("rewrite")}>
          <div className="mini-diff"><div><small>Original</small><del>Responsible for backend API development using Spring Boot.</del></div><div><small>Tailored</small><ins>Rebuilt payment callbacks with Spring Boot, reducing P99 latency from 820ms to 210ms.</ins></div></div>
          <p className="fine">Missing facts are requested before they are added.</p>
        </DashboardCard>
        <DashboardCard title="Mock interview" meta="6 questions · 40 min" text="Practise a role-specific question set and record each answer." onExplore={() => navigate("interview")}>
          <div className="camera"><span>CAMERA PREVIEW</span><small><i /> REC 00:00</small></div>
        </DashboardCard>
      </div>
      <div className="dash-grid two">
        <DashboardCard title="My target jobs" meta={selected.length + " targets · 25% average"} text="Track resume tailoring, interview practice and application stage." onExplore={() => navigate("targets")}>
          {selected.map((job) => <div className="mini-target" key={job.id}><div><b>{job.title}</b><span>25%</span></div><small>{job.company}</small><div className="progress"><i style={{ width: "25%" }} /></div><p><em>Not applied</em><em>Resume pending</em><em>Interview pending</em></p></div>)}
        </DashboardCard>
        <DashboardCard title="Profile & career intent" meta="Updated 3 September" text="Maintain the profile fields and constraints used by matching." onExplore={() => navigate("profile")}>
          <table><tbody><tr><td>Target roles</td><td>Backend Developer</td></tr><tr><td>Target industry</td><td>Financial Technology</td></tr><tr><td>Work modes</td><td>Hybrid, On-site</td></tr><tr><td>Profile status</td><td>2 fields to review</td></tr><tr><td>Notes</td><td>Payment and trading systems</td></tr></tbody></table>
        </DashboardCard>
      </div>
    </>
  );
}
