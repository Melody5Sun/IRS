import { useGo } from "../../app/routes";
import { useI18n } from "../../i18n/LanguageProvider";
import { formatDateTime } from "../../lib/format";
import { ERROR_RED, TODO_AMBER } from "./constants";
import { profileErrorMessage } from "./messages";
import { ProfileDialogs } from "./ProfileDialogs";
import { ResumeSourcePanel } from "./ResumeSourcePanel";
import { IntentSection } from "./sections/IntentSection";
import { PersonalSection } from "./sections/PersonalSection";
import {
  AdditionalSection, CertificatesSection, EducationSection, ExperienceSection,
  ProjectsSection, ResearchSection, SkillsSection,
} from "./sections/ResumeSections";
import { scrollToField, useProfileEditor } from "./useProfileEditor";
import { validateProfile } from "./validation";
import { ValidationProvider } from "./ValidationContext";

export function ProfilePage() {
  const { lang, t } = useI18n();
  const go = useGo();
  const editor = useProfileEditor();
  const { draft, dirty, saving, updatedAt } = editor;

  const header = (description: string) => <header className="profile-page-header">
    <div className="eyebrow">{t("profile.eyebrow")}</div>
    <h1>{t("profile.title")}</h1>
    <p>{description}</p>
  </header>;

  if (editor.loading) return <div className="page profile-page">{header(t("profile.loadingText"))}<div className="profile-state">{t("profile.loading")}</div></div>;

  const issues = draft ? validateProfile(draft) : [];
  const color = editor.attempted ? ERROR_RED : TODO_AMBER;
  const count = issues.length;
  const status = saving ? t("profile.status.saving")
    : count ? (dirty ? t("profile.status.unsavedRemaining", { count }) : t("profile.status.remaining", { count }))
    : dirty ? t("profile.status.unsaved")
    : updatedAt ? t("profile.status.saved", { date: formatDateTime(updatedAt, lang) })
    : t("profile.status.ready");

  return (
    <div className="page profile-page">
      {header(t("profile.description"))}
      <div className="profile-content">
        <ResumeSourcePanel editor={editor} />

        {editor.error && <div className="form-message error" role="alert">{profileErrorMessage(editor.error, t)}</div>}

        {draft && <ValidationProvider issues={issues} color={color}>
          {count > 0 && <div className="profile-todo-summary" style={{ color }}>
            <span>{t("profile.todoBefore")}<b>{count}</b>{t("profile.todoAfter")}</span>
            <button onClick={() => scrollToField(issues[0].id)}>{t("profile.jumpToFirst")}</button>
          </div>}
          <div className="forms">
            <div>
              <PersonalSection editor={editor} draft={draft} />
              <IntentSection editor={editor} draft={draft} />
              <EducationSection editor={editor} draft={draft} />
              <SkillsSection editor={editor} draft={draft} />
            </div>
            <div>
              <ExperienceSection editor={editor} draft={draft} />
              <ProjectsSection editor={editor} draft={draft} />
              <ResearchSection editor={editor} draft={draft} />
              <CertificatesSection editor={editor} draft={draft} />
              <AdditionalSection editor={editor} draft={draft} />
            </div>
          </div>
          <div className={"profile-savebar " + (dirty ? "dirty" : "")}>
            <div>
              <button className="primary" disabled={saving} onClick={editor.save}>{saving ? t("profile.saving") : t("profile.save")}</button>
              <button className="secondary" onClick={() => go("jobs")}>{t("profile.goJobs")}</button>
              <button className="ghost" onClick={() => go("dashboard")}>{t("profile.backDashboard")}</button>
            </div>
            <span style={{ color: count ? color : undefined }}>{status}</span>
          </div>
        </ValidationProvider>}
      </div>
      {editor.toast && <div className="profile-toast" role="status">{t(editor.toast.key, editor.toast.vars)}</div>}
      <ProfileDialogs editor={editor} />
    </div>
  );
}
