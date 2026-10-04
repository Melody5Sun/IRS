import { useState, type ReactNode } from "react";
import { AppHeader } from "./components/layout/AppHeader";
import { INITIAL_TARGET_IDS } from "./mocks/data";
import { DashboardPage } from "./pages/DashboardPage";
import { InterviewPage } from "./pages/InterviewPage";
import { JobsPage } from "./pages/JobsPage";
import { ProfilePage } from "./pages/ProfilePage";
import { RewritePage } from "./pages/RewritePage";
import { TargetsPage } from "./pages/TargetsPage";
import "./styles.css";
import type { Page } from "./types/domain";

const VALID_PAGES: Page[] = ["dashboard", "profile", "jobs", "rewrite", "interview", "targets"];

function pageFromHash(): Page {
  const value = window.location.hash.slice(1) as Page;
  return VALID_PAGES.includes(value) ? value : "dashboard";
}

export function App() {
  const [page, setPage] = useState<Page>(pageFromHash);
  const [targetIds, setTargetIds] = useState<number[]>(INITIAL_TARGET_IDS);

  const navigate = (nextPage: Page) => {
    setPage(nextPage);
    window.location.hash = nextPage;
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  let content: ReactNode = <DashboardPage navigate={navigate} targetIds={targetIds} />;
  if (page === "profile") content = <ProfilePage />;
  if (page === "jobs") content = <JobsPage targetIds={targetIds} setTargetIds={setTargetIds} navigate={navigate} />;
  if (page === "rewrite") content = <RewritePage />;
  if (page === "interview") content = <InterviewPage />;
  if (page === "targets") content = <TargetsPage targetIds={targetIds} setTargetIds={setTargetIds} navigate={navigate} />;

  return (
    <div className="shell">
      <AppHeader page={page} navigate={navigate} />
      {content}
      <footer className="site-footer">CareerPilot · Interactive frontend prototype · Sample data only</footer>
      <button className="float" title="Open job recommendations" onClick={() => navigate("jobs")}>↗<small>00</small></button>
    </div>
  );
}
