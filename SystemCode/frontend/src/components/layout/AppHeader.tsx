import { useEffect, useState } from "react";
import { jobsApi } from "../../api/jobs";
import { ROUTES, useGo } from "../../app/routes";
import { useI18n, type Lang, type Translate } from "../../i18n/LanguageProvider";
import { localeOf } from "../../lib/format";
import type { Page } from "../../types/domain";

type LibraryStatus = { synced_at: string | null; active_job_count: number };

const LANGUAGES: Array<[Lang, string]> = [["en", "EN"], ["zh", "中文"]];

export function AppHeader({ page }: { page: Page }) {
  const { lang, setLang, t } = useI18n();
  const go = useGo();
  const [libraryStatus, setLibraryStatus] = useState<LibraryStatus | null>(null);

  useEffect(() => {
    let active = true;
    jobsApi.getLibraryStatus().then((status) => {
      if (active) setLibraryStatus(status);
    }).catch(() => undefined);
    return () => { active = false; };
  }, []);

  const crumbKey = ROUTES[page].crumbKey;

  return (
    <>
      <div className="topbar">
        <button className="brand" onClick={() => go("dashboard")}>
          <span>CareerPilot</span>
          <small>{t("app.tagline")}</small>
        </button>
        <div className="topbar-account">
          <div className="userbar">
            <span>{libraryLabel(libraryStatus, lang, t)}</span>
            <i />
            <span>Alex Chen · NUS Computing</span>
            <b>AC</b>
          </div>
          <div className="seg lang-switch" role="group" aria-label={t("app.language")}>
            {LANGUAGES.map(([value, label]) => (
              <button key={value} className={lang === value ? "active" : ""} aria-pressed={lang === value} onClick={() => setLang(value)}>{label}</button>
            ))}
          </div>
        </div>
      </div>
      {crumbKey && (
        <div className="crumb">
          <button onClick={() => go("dashboard")}>{t("app.backToDashboard")}</button>
          <span>{t(crumbKey)}</span>
        </div>
      )}
    </>
  );
}

function libraryLabel(status: LibraryStatus | null, lang: Lang, t: Translate) {
  if (!status) return t("app.libraryUnavailable");
  if (!status.synced_at) return t("app.libraryActive", { count: status.active_job_count });
  const date = new Date(status.synced_at);
  const today = new Date();
  const sameDay = date.getFullYear() === today.getFullYear() && date.getMonth() === today.getMonth() && date.getDate() === today.getDate();
  const locale = localeOf(lang);
  const when = sameDay
    ? t("app.todayAt", { time: new Intl.DateTimeFormat(locale, { hour: "2-digit", minute: "2-digit", hour12: false }).format(date) })
    : new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false }).format(date);
  return t("app.librarySynced", { when, count: status.active_job_count });
}
