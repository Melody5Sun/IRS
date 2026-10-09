import { useI18n } from "../../i18n/LanguageProvider";
import type { InterviewQuestion } from "../../types/api";
import { answerText, difficultyLabel, formatClock, questionText, typeLabel } from "./labels";
import { interviewErrorMessage } from "./messages";
import type { InterviewSession } from "./useInterviewSession";

// 录制视图：左侧摄像头与录制控制，右侧题目、英文转写和参考答案
export function RecordingView({ session, question }: { session: InterviewSession; question: InterviewQuestion }) {
  const { lang, t } = useI18n();
  const { recorder, questions, active, selectedTarget, cameraOn, transcribing, transcript, stats, error } = session;
  const { recording, seconds } = recorder;
  const clock = formatClock(seconds);
  const answer = session.recordings[question.id];

  return <>
    <header className="interview-header recording-header">
      <div className="interview-heading">
        <div className="eyebrow">{t("interview.recordEyebrow")}</div>
        <h1>{t("interview.recordTitle")}</h1>
        <div className="interview-target-line"><span>{selectedTarget?.company} · {selectedTarget?.title} · {typeLabel(question.question_type, t)}</span></div>
      </div>
      <div className="interview-header-actions">
        <div className="interview-counter"><strong>{active + 1} / {questions.length}</strong><span>{t("interview.currentQuestion")}</span></div>
        <div className="interview-counter"><strong>{clock}</strong><span>{t("interview.answerTime")}</span></div>
      </div>
    </header>
    <div className="interview-nav">
      <button className="secondary" disabled={active === 0} onClick={() => session.chooseQuestion(active - 1)}>{t("interview.previous")}</button>
      <button className="secondary" disabled={active === questions.length - 1} onClick={() => session.chooseQuestion(active + 1)}>{t("interview.next")}</button>
      <button className="ghost" onClick={session.backToBank}>{t("interview.backToBank")}</button>
      <span>{t("interview.bankProgress", { answered: session.answeredCount, total: questions.length })}</span>
    </div>
    {error && <div className="form-message error">{interviewErrorMessage(error, t)}</div>}
    <div className="interview-record-grid">
      <section className="recording-column">
        <div className="camera-plate">
          {cameraOn ? <video ref={recorder.videoRef} muted playsInline /> : <div className="camera-placeholder"><span>{t("interview.cameraOff")}</span><small>{t("interview.cameraOffHint")}</small></div>}
          <div className="recording-status">{recording && <i />}<span>{recording ? `REC ${clock}` : `READY ${clock}`}</span></div>
          <div className="interviewer-tile">{t("interview.interviewerTile")}<br />{t("interview.interviewerTilePreview")}</div>
        </div>
        <div className="recording-controls">
          <button className="primary" disabled={transcribing} onClick={recording ? recorder.stop : session.startRecording}>{recording ? t("interview.stop") : transcribing ? t("interview.transcribing") : t("interview.start")}</button>
          <button className="secondary" disabled={recording} onClick={session.resetAnswer}>{t("interview.recordAgain")}</button>
          <label><input type="checkbox" checked={cameraOn} disabled={recording} onChange={(event) => session.setCameraOn(event.target.checked)} />{t("interview.enableCamera")}</label>
        </div>
        {answer && (answer.video ? <video className="answer-video" controls src={answer.url} /> : <audio className="answer-audio" controls src={answer.url} />)}
        <div className="recording-metrics">
          <span>{transcript ? t("interview.wpm", { wpm: stats.wpm }) : t("interview.wpmPending")}</span>
          <span>{transcript ? t("interview.fillers", { count: stats.fillers }) : t("interview.fillersPending")}</span>
          <span>{t("interview.localOnly")}</span>
        </div>
      </section>
      <section className="answer-column">
        <div className="question-panel">
          <div className="eyebrow">{t("interview.currentQuestionLabel", { type: typeLabel(question.question_type, t), difficulty: difficultyLabel(question.difficulty_level, t) })}</div>
          <h2>{questionText(question, lang)}</h2>
          <div className="question-role">{t("interview.allocatedRole", { role: question.allocated_role || question.roles.join(", ") })}</div>
        </div>
        <div className="transcript-panel">
          <div><h3>{t("interview.transcriptTitle")}</h3><span>{transcribing ? t("interview.transcriptBusy") : transcript ? t("interview.transcriptDone") : t("interview.transcriptPending")}</span></div>
          <textarea value={transcript} onChange={(event) => session.setTranscripts((current) => ({ ...current, [question.id]: event.target.value }))} placeholder={t("interview.transcriptPlaceholder")} />
        </div>
        <details className="reference-answer"><summary>{t("interview.showAnswer")}</summary><div>{answerText(question, lang)}</div></details>
      </section>
    </div>
  </>;
}
