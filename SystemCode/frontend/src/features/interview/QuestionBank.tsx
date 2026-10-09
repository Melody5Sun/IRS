import { useI18n } from "../../i18n/LanguageProvider";
import { difficultyLabel, questionText, typeLabel } from "./labels";
import { interviewErrorMessage } from "./messages";
import type { InterviewSession } from "./useInterviewSession";

// 题库视图：选择目标岗位、换一组题、从任意题开始练习
export function QuestionBank({ session }: { session: InterviewSession }) {
  const { lang, t } = useI18n();
  const { targets, selectedJobId, questions, transcripts, sample, sampling, error } = session;
  return <>
    <header className="interview-header">
      <div className="interview-heading">
        <div className="eyebrow">{t("interview.bankEyebrow")}</div>
        <h1>{t("interview.bankTitle")}</h1>
        <div className="interview-target-line">
          <select value={selectedJobId ?? ""} onChange={(event) => session.setSelectedJobId(Number(event.target.value))}>
            {targets.map((target) => <option key={target.job_id} value={target.job_id}>{target.company} · {target.title}</option>)}
          </select>
          <span>{t("interview.questionCount", { count: questions.length })}</span>
        </div>
      </div>
      <div className="interview-header-actions">
        <div className="interview-counter"><strong>{session.answeredCount} / {questions.length}</strong><span>{t("interview.answered")}</span></div>
        <button className="secondary" disabled={sampling} onClick={() => selectedJobId && session.loadQuestions(selectedJobId, questions.map((item) => item.id))}>{sampling ? t("interview.loading") : t("interview.refresh")}</button>
        <button className="primary" disabled={!questions.length} onClick={() => session.chooseQuestion(0)}>{t("interview.startFirst")}</button>
      </div>
    </header>
    <p className="interview-intro">{t("interview.intro")}</p>
    {error && <div className="form-message error">{interviewErrorMessage(error, t)}</div>}
    {sample?.warnings.map((warning) => <div className="interview-warning" key={warning}>{warning}</div>)}
    {sampling && !sample && <div className="interview-state"><h2>{t("interview.building")}</h2></div>}
    <div className="question-bank">{questions.map((item, index) => (
      <article className="bank-question" key={item.id}>
        <div className="bank-number">{String(item.sequence).padStart(2, "0")}</div>
        <div className="bank-main">
          <div className="bank-tags"><span>{typeLabel(item.question_type, t)}</span><em>{difficultyLabel(item.difficulty_level, t)}</em>{item.allocated_role && <small>{item.allocated_role}</small>}</div>
          <h2>{questionText(item, lang)}</h2>
          <p>{t("interview.questionMeta", { roles: item.roles.join(" · "), source: item.source })}</p>
        </div>
        <div className="bank-action">
          <span>{transcripts[item.id] ? t("interview.statusAnswered") : t("interview.statusNotAnswered")}</span>
          <button className="primary" onClick={() => session.chooseQuestion(index)}>{transcripts[item.id] ? t("interview.practiseAgain") : t("interview.practise")}</button>
        </div>
      </article>
    ))}</div>
  </>;
}
