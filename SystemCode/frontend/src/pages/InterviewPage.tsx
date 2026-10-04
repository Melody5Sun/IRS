import { useState } from "react";
import { PageFrame } from "../components/layout/PageFrame";
import { QUESTIONS } from "../mocks/data";

export function InterviewPage() {
  const [active, setActive] = useState(0);
  const [recording, setRecording] = useState(false);
  const question = QUESTIONS[active];
  return (
    <PageFrame eyebrow="STEP 04 · ROLE-SPECIFIC MOCK INTERVIEW" title="Mock interview" description="Practise a balanced set for the selected role, record an answer, and review the English transcript with a reference answer.">
      <div className="workspace interview">
        <aside>
          <div className="aside-head"><h3>Question set</h3><span>{QUESTIONS.length} questions</span></div>
          {QUESTIONS.map((item, index) => <button className={active === index ? "active" : ""} onClick={() => { setActive(index); setRecording(false); }} key={item.id}><span>{String(index + 1).padStart(2, "0")}</span><b>{item.text}</b><small>{item.type} · {item.difficulty}</small></button>)}
        </aside>
        <main className="editor">
          <div className="question"><div><span className="eyebrow">QUESTION {active + 1} OF {QUESTIONS.length}</span><h2>{question.text}</h2></div><em>{question.difficulty}</em></div>
          <div className="video"><span>CAMERA PREVIEW</span><small><i className={recording ? "live" : ""} /> {recording ? "REC 00:18" : "READY"}</small></div>
          <div className="record"><button className={recording ? "secondary" : "primary"} onClick={() => setRecording(!recording)}>{recording ? "Stop recording" : "Start recording"}</button><button className="ghost">Replay</button></div>
          <label className="field"><span>English transcript</span><textarea placeholder="Your transcribed answer will appear here after recording..." /></label>
          <details><summary>Show reference answer</summary><p>{question.answer}</p></details>
        </main>
      </div>
    </PageFrame>
  );
}
