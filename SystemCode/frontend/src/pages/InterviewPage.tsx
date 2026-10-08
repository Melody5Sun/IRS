import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError } from "../api";
import { interviewApi } from "../api/interview";
import { targetsApi } from "../api/targets";
import type { InterviewQuestion, InterviewSample, TargetJob } from "../types/api";

type ViewMode = "bank" | "record";

function typeLabel(value: InterviewQuestion["question_type"]) {
  return value === "basic_programming" ? "Basic programming" : "Role specific";
}

function difficultyLabel(value: InterviewQuestion["difficulty_level"]) {
  return value === "not_stated" ? "Not stated" : value[0].toUpperCase() + value.slice(1);
}

function formatClock(seconds: number) {
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function errorMessage(error: unknown) {
  if (!(error instanceof ApiError)) return "Unable to connect to the backend. Check that the API server is running.";
  if (error.status === 409) return "Interview questions are unavailable because this job has not been matched to a standard role.";
  if (error.status === 413) return "The recording is larger than 25 MB. Please record a shorter answer.";
  if (error.status === 422) return "The recording format is not supported. Please record the answer again.";
  if (error.status === 503) return "English transcription is not configured on the backend.";
  if (error.status === 502) return "Transcription is temporarily unavailable. Please try again later.";
  return typeof error.body.detail === "string" ? error.body.detail : "The request could not be completed.";
}

export function InterviewPage() {
  const [targets, setTargets] = useState<TargetJob[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [sample, setSample] = useState<InterviewSample | null>(null);
  const [mode, setMode] = useState<ViewMode>("bank");
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(true);
  const [sampling, setSampling] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [cameraOn, setCameraOn] = useState(true);
  const [seconds, setSeconds] = useState(0);
  const [transcripts, setTranscripts] = useState<Record<number, string>>({});
  const [recordings, setRecordings] = useState<Record<number, { url: string; video: boolean }>>({});
  const [error, setError] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const selectedTarget = targets.find((target) => target.job_id === selectedJobId) ?? null;
  const questions = sample?.questions ?? [];
  const question = questions[active] ?? null;
  const answeredCount = questions.filter((item) => Boolean(transcripts[item.id])).length;

  const stopStream = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  };

  const ensureStream = async (withVideo: boolean) => {
    const current = streamRef.current;
    if (current?.getAudioTracks().length && (!withVideo || current.getVideoTracks().length)) return current;
    stopStream();
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: withVideo });
    streamRef.current = stream;
    if (withVideo && videoRef.current) {
      videoRef.current.srcObject = stream;
      await videoRef.current.play().catch(() => undefined);
    }
    return stream;
  };

  const loadQuestions = async (jobId: number, exclude: number[] = []) => {
    setSampling(true); setError(null);
    try {
      const result = await interviewApi.sample(jobId, {
        count: 10,
        difficulty_mix: { easy: 4, medium: 4, hard: 2 },
        exclude_question_ids: exclude,
      });
      setSample(result); setActive(0); setMode("bank");
    } catch (reason) { setError(errorMessage(reason)); setSample(null); }
    finally { setSampling(false); }
  };

  useEffect(() => {
    let activeRequest = true;
    targetsApi.list().then((items) => {
      if (!activeRequest) return;
      setTargets(items);
      setSelectedJobId(items[0]?.job_id ?? null);
    }).catch((reason) => activeRequest && setError(errorMessage(reason)))
      .finally(() => activeRequest && setLoading(false));
    return () => { activeRequest = false; };
  }, []);

  useEffect(() => {
    if (selectedJobId) loadQuestions(selectedJobId);
  }, [selectedJobId]);

  useEffect(() => {
    if (mode !== "record") { stopStream(); return; }
    if (cameraOn) ensureStream(true).catch((reason) => setError(reason instanceof Error ? reason.message : "Camera access was denied."));
    else stopStream();
  }, [cameraOn, mode, active]);

  useEffect(() => () => {
    stopStream();
    if (timerRef.current) clearInterval(timerRef.current);
    Object.values(recordings).forEach((recording) => URL.revokeObjectURL(recording.url));
  }, []);

  const finishRecording = async (blob: Blob, recordedQuestion: InterviewQuestion, hasVideo: boolean) => {
    const url = URL.createObjectURL(blob);
    setRecordings((current) => {
      if (current[recordedQuestion.id]) URL.revokeObjectURL(current[recordedQuestion.id].url);
      return { ...current, [recordedQuestion.id]: { url, video: hasVideo } };
    });
    if (!selectedJobId) return;
    setTranscribing(true); setError(null);
    try {
      const result = await interviewApi.transcribe(selectedJobId, recordedQuestion.id, blob);
      setTranscripts((current) => ({ ...current, [recordedQuestion.id]: result.transcript }));
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setTranscribing(false); }
  };

  const startRecording = async () => {
    if (!question || recording) return;
    setError(null); setSeconds(0); chunksRef.current = [];
    try {
      const stream = await ensureStream(cameraOn);
      const hasVideo = cameraOn && stream.getVideoTracks().length > 0;
      const recordingStream = hasVideo ? stream : new MediaStream(stream.getAudioTracks());
      const mimeType = hasVideo ? "video/webm" : "audio/webm";
      const recorder = new MediaRecorder(recordingStream, MediaRecorder.isTypeSupported(mimeType) ? { mimeType } : undefined);
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => { if (event.data.size) chunksRef.current.push(event.data); };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        void finishRecording(blob, question, hasVideo);
      };
      recorder.start(); setRecording(true);
      timerRef.current = setInterval(() => setSeconds((value) => value + 1), 1000);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Microphone access was denied."); }
  };

  const stopRecording = () => {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
    setRecording(false);
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
  };

  const chooseQuestion = (index: number) => {
    if (recording) stopRecording();
    setActive(index); setSeconds(0); setMode("record");
  };

  const transcript = question ? transcripts[question.id] ?? "" : "";
  const wordStats = useMemo(() => {
    const words = transcript.trim() ? transcript.trim().split(/\s+/) : [];
    const fillers = words.filter((word) => /^(um+|uh+|erm+|like)$/i.test(word.replace(/[^a-z]/gi, ""))).length;
    return { wpm: seconds > 0 ? Math.round(words.length * 60 / seconds) : 0, fillers };
  }, [seconds, transcript]);

  if (loading) return <div className="interview-state"><h2>Loading target jobs...</h2></div>;
  if (!targets.length) return <div className="interview-page"><header className="interview-header"><div><div className="eyebrow">STEP 04 · ROLE-SPECIFIC MOCK INTERVIEW</div><h1>Mock interview · Question bank</h1></div></header><div className="interview-state"><h2>No target jobs yet</h2><p>Add a role from Job recommendations before generating a role-specific interview set.</p></div></div>;

  return <div className="interview-page">
    {mode === "bank" ? <>
      <header className="interview-header">
        <div className="interview-heading"><div className="eyebrow">STEP 04 · TARGET-JD QUESTION SET</div><h1>Mock interview · Question bank</h1><div className="interview-target-line"><select value={selectedJobId ?? ""} onChange={(event) => setSelectedJobId(Number(event.target.value))}>{targets.map((target) => <option key={target.job_id} value={target.job_id}>{target.company} · {target.title}</option>)}</select><span>{questions.length} questions · English practice</span></div></div>
        <div className="interview-header-actions"><div className="interview-counter"><strong>{answeredCount} / {questions.length}</strong><span>answered</span></div><button className="secondary" disabled={sampling} onClick={() => selectedJobId && loadQuestions(selectedJobId, questions.map((item) => item.id))}>{sampling ? "Loading..." : "Refresh set"}</button><button className="primary" disabled={!questions.length} onClick={() => chooseQuestion(0)}>Start from question 1 →</button></div>
      </header>
      <p className="interview-intro">Questions are selected from the standard roles matched to this target job. Practise in any order, record an answer, then review the English transcript and reference answer.</p>
      {error && <div className="form-message error">{error}</div>}
      {sample?.warnings.map((warning) => <div className="interview-warning" key={warning}>{warning}</div>)}
      {sampling && !sample && <div className="interview-state"><h2>Building question set...</h2></div>}
      <div className="question-bank">{questions.map((item, index) => <article className="bank-question" key={item.id}><div className="bank-number">{String(item.sequence).padStart(2, "0")}</div><div className="bank-main"><div className="bank-tags"><span>{typeLabel(item.question_type)}</span><em>{difficultyLabel(item.difficulty_level)}</em>{item.allocated_role && <small>{item.allocated_role}</small>}</div><h2>{item.question_text_en || item.question_text}</h2><p>{item.roles.join(" · ")} · Source: {item.source}</p></div><div className="bank-action"><span>{transcripts[item.id] ? "Answered" : "Not answered"}</span><button className="primary" onClick={() => chooseQuestion(index)}>{transcripts[item.id] ? "Practise again →" : "Practise question →"}</button></div></article>)}</div>
    </> : question && <>
      <header className="interview-header recording-header"><div className="interview-heading"><div className="eyebrow">STEP 04 · RECORD ANSWER</div><h1>Mock interview</h1><div className="interview-target-line"><span>{selectedTarget?.company} · {selectedTarget?.title} · {typeLabel(question.question_type)}</span></div></div><div className="interview-header-actions"><div className="interview-counter"><strong>{active + 1} / {questions.length}</strong><span>current question</span></div><div className="interview-counter"><strong>{formatClock(seconds)}</strong><span>answer time</span></div></div></header>
      <div className="interview-nav"><button className="secondary" disabled={active === 0} onClick={() => chooseQuestion(active - 1)}>← Previous</button><button className="secondary" disabled={active === questions.length - 1} onClick={() => chooseQuestion(active + 1)}>Next →</button><button className="ghost" onClick={() => { if (recording) stopRecording(); setMode("bank"); }}>Back to question bank</button><span>Question-bank progress {answeredCount} / {questions.length} answered</span></div>
      {error && <div className="form-message error">{error}</div>}
      <div className="interview-record-grid">
        <section className="recording-column"><div className="camera-plate">{cameraOn ? <video ref={videoRef} muted playsInline /> : <div className="camera-placeholder"><span>Camera is off</span><small>Enable camera for video practice</small></div>}<div className="recording-status">{recording && <i />}<span>{recording ? `REC ${formatClock(seconds)}` : `READY ${formatClock(seconds)}`}</span></div><div className="interviewer-tile">AI interviewer<br />preview</div></div><div className="recording-controls"><button className="primary" disabled={transcribing} onClick={recording ? stopRecording : startRecording}>{recording ? "Stop and transcribe" : transcribing ? "Transcribing..." : "Start recording"}</button><button className="secondary" disabled={recording} onClick={() => { setSeconds(0); setTranscripts((current) => { const next = { ...current }; delete next[question.id]; return next; }); setRecordings((current) => { const next = { ...current }; if (next[question.id]) URL.revokeObjectURL(next[question.id].url); delete next[question.id]; return next; }); }}>Record again</button><label><input type="checkbox" checked={cameraOn} disabled={recording} onChange={(event) => setCameraOn(event.target.checked)} />Enable camera</label></div>{recordings[question.id] && (recordings[question.id].video ? <video className="answer-video" controls src={recordings[question.id].url} /> : <audio className="answer-audio" controls src={recordings[question.id].url} />)}<div className="recording-metrics"><span>{transcript ? `${wordStats.wpm} words/min` : "Speech rate after transcription"}</span><span>{transcript ? `${wordStats.fillers} filler words` : "Filler words after transcription"}</span><span>Recording remains in this browser</span></div></section>
        <section className="answer-column"><div className="question-panel"><div className="eyebrow">CURRENT QUESTION · {typeLabel(question.question_type)} · {difficultyLabel(question.difficulty_level)}</div><h2>{question.question_text_en || question.question_text}</h2><div className="question-role">Allocated role · {question.allocated_role || question.roles.join(", ")}</div></div><div className="transcript-panel"><div><h3>English transcript</h3><span>{transcribing ? "Transcribing recorded answer..." : transcript ? "Completed · editable" : "Available after recording"}</span></div><textarea value={transcript} onChange={(event) => setTranscripts((current) => ({ ...current, [question.id]: event.target.value }))} placeholder="Your English transcript will appear here after the recording is uploaded." /></div><details className="reference-answer"><summary>Show reference answer</summary><div>{question.standard_answer_en || question.standard_answer}</div></details></section>
      </div>
    </>}
  </div>;
}
