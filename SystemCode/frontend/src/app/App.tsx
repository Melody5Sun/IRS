import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { AppHeader } from "../components/layout/AppHeader";
import { FlowMenu } from "../components/layout/FlowMenu";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { InterviewPage } from "../features/interview/InterviewPage";
import { JobsPage } from "../features/jobs/JobsPage";
import { ProfilePage } from "../features/profile/ProfilePage";
import { RewritePage } from "../features/rewrite/RewritePage";
import { TargetsPage } from "../features/targets/TargetsPage";
import { useI18n } from "../i18n/LanguageProvider";
import { ROUTES, pageFromLegacyHash, pageFromPath } from "./routes";

export function App() {
  const { t } = useI18n();
  const { pathname, hash } = useLocation();
  const navigate = useNavigate();
  const page = pageFromPath(pathname);

  // 旧书签 /#jobs → /jobs
  useEffect(() => {
    const legacy = pageFromLegacyHash(hash);
    if (pathname === "/" && legacy && legacy !== "dashboard") navigate(ROUTES[legacy].path, { replace: true });
  }, [hash, navigate, pathname]);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [pathname]);

  return (
    <div className="shell">
      <AppHeader page={page ?? "dashboard"} />
      <Routes>
        <Route path={ROUTES.dashboard.path} element={<DashboardPage />} />
        <Route path={ROUTES.profile.path} element={<ProfilePage />} />
        <Route path={ROUTES.jobs.path} element={<JobsPage />} />
        <Route path={ROUTES.rewrite.path} element={<RewritePage />} />
        <Route path={ROUTES.interview.path} element={<InterviewPage />} />
        <Route path={ROUTES.targets.path} element={<TargetsPage />} />
        <Route path="*" element={<Navigate to={ROUTES.dashboard.path} replace />} />
      </Routes>
      {page && !ROUTES[page].hideFooter && <footer className="site-footer">{t("app.footer")}</footer>}
      <FlowMenu page={page ?? "dashboard"} />
    </div>
  );
}
