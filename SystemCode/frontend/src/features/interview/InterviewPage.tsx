import { useI18n } from "../../i18n/LanguageProvider";
import { QuestionBank } from "./QuestionBank";
import { RecordingView } from "./RecordingView";
import { useInterviewSession } from "./useInterviewSession";

export function InterviewPage() {
  const { t } = useI18n();
  const session = useInterviewSession();

  if (session.loading) return <div className="interview-state"><h2>{t("interview.loadingTargets")}</h2></div>;
  if (!session.targets.length) return <div className="interview-page">
    <header className="interview-header"><div><div className="eyebrow">{t("interview.emptyEyebrow")}</div><h1>{t("interview.bankTitle")}</h1></div></header>
    <div className="interview-state"><h2>{t("interview.emptyTitle")}</h2><p>{t("interview.emptyText")}</p></div>
  </div>;

  return <div className="interview-page">
    {session.mode === "bank" ? <QuestionBank session={session} /> : session.question && <RecordingView session={session} question={session.question} />}
  </div>;
}
