import type { Page } from "../../types/domain";

const PAGE_LABELS: Record<Page, string> = {
  dashboard: "",
  profile: "Resume profile & career intent",
  jobs: "Job recommendations",
  rewrite: "Resume tailoring",
  interview: "Mock interview",
  targets: "My target jobs",
};

export function AppHeader({ page, navigate }: { page: Page; navigate: (page: Page) => void }) {
  return (
    <>
      <div className="topbar">
        <button className="brand" onClick={() => navigate("dashboard")}>
          <span>CareerPilot</span>
          <small>IT JOB REASONING SYSTEM</small>
        </button>
        <div className="userbar">
          <span>JD library synced today at 07:40 · 148 active</span>
          <i />
          <span>Alex Chen · NUS Computing</span>
          <b>AC</b>
        </div>
      </div>
      {page !== "dashboard" && (
        <div className="crumb">
          <button onClick={() => navigate("dashboard")}>← Back to dashboard</button>
          <span>{PAGE_LABELS[page]}</span>
        </div>
      )}
    </>
  );
}
