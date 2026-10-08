import { useEffect, useState } from "react";
import { jobsApi } from "../../api/jobs";
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
  const [libraryStatus, setLibraryStatus] = useState<string>("JD library status unavailable");

  useEffect(() => {
    let active = true;
    jobsApi.getLibraryStatus().then((status) => {
      if (!active) return;
      if (!status.synced_at) {
        setLibraryStatus(`JD library · ${status.active_job_count} active`);
        return;
      }
      const date = new Date(status.synced_at);
      const today = new Date();
      const sameDay = date.getFullYear() === today.getFullYear() && date.getMonth() === today.getMonth() && date.getDate() === today.getDate();
      const when = sameDay
        ? `today at ${new Intl.DateTimeFormat("en-SG", { hour: "2-digit", minute: "2-digit", hour12: false }).format(date)}`
        : new Intl.DateTimeFormat("en-SG", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false }).format(date);
      setLibraryStatus(`JD library synced ${when} · ${status.active_job_count} active`);
    }).catch(() => undefined);
    return () => { active = false; };
  }, []);

  return (
    <>
      <div className="topbar">
        <button className="brand" onClick={() => navigate("dashboard")}>
          <span>CareerPilot</span>
          <small>IT JOB REASONING SYSTEM</small>
        </button>
        <div className="userbar">
          <span>{libraryStatus}</span>
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
