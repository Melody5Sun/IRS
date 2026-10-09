import { useEffect, useMemo, useRef, useState } from "react";
import { interviewApi } from "../../api/interview";
import { targetsApi } from "../../api/targets";
import type { InterviewQuestion, InterviewSample, TargetJob } from "../../types/api";
import { wordStats } from "./labels";
import type { InterviewFailure } from "./messages";
import { useMediaRecorder } from "./useMediaRecorder";

type ViewMode = "bank" | "record";
type Recording = { url: string; video: boolean };

// 模拟面试页的状态与接口调用：目标岗位、抽题、录制、转写
export function useInterviewSession() {
  const recorder = useMediaRecorder();
  const [targets, setTargets] = useState<TargetJob[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [sample, setSample] = useState<InterviewSample | null>(null);
  const [mode, setMode] = useState<ViewMode>("bank");
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(true);
  const [sampling, setSampling] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [cameraOn, setCameraOn] = useState(true);
  const [transcripts, setTranscripts] = useState<Record<number, string>>({});
  const [recordings, setRecordings] = useState<Record<number, Recording>>({});
  const [error, setError] = useState<InterviewFailure | null>(null);
  // 卸载时释放录音的 object URL，用 ref 拿到最新的录音表
  const recordingsRef = useRef(recordings);
  recordingsRef.current = recordings;

  const selectedTarget = targets.find((target) => target.job_id === selectedJobId) ?? null;
  const questions = sample?.questions ?? [];
  const question = questions[active] ?? null;
  const answeredCount = questions.filter((item) => Boolean(transcripts[item.id])).length;

  const loadQuestions = async (jobId: number, exclude: number[] = []) => {
    setSampling(true); setError(null);
    try {
      const result = await interviewApi.sample(jobId, {
        count: 10,
        difficulty_mix: { easy: 4, medium: 4, hard: 2 },
        exclude_question_ids: exclude,
      });
      setSample(result); setActive(0); setMode("bank");
    } catch (reason) { setError({ reason }); setSample(null); }
    finally { setSampling(false); }
  };

  useEffect(() => {
    let activeRequest = true;
    targetsApi.list().then((items) => {
      if (!activeRequest) return;
      setTargets(items);
      setSelectedJobId(items[0]?.job_id ?? null);
    }).catch((reason) => activeRequest && setError({ reason }))
      .finally(() => activeRequest && setLoading(false));
    return () => { activeRequest = false; };
  }, []);

  useEffect(() => {
    if (selectedJobId) loadQuestions(selectedJobId);
  }, [selectedJobId]);

  // 只有录制视图才占用摄像头；切题时重新确认流可用
  useEffect(() => {
    if (mode !== "record") { recorder.stopStream(); return; }
    if (cameraOn) recorder.ensureStream(true).catch((reason) => setError({ reason, device: "camera" }));
    else recorder.stopStream();
  }, [cameraOn, mode, active]);

  useEffect(() => () => {
    Object.values(recordingsRef.current).forEach((recording) => URL.revokeObjectURL(recording.url));
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
    } catch (reason) { setError({ reason }); }
    finally { setTranscribing(false); }
  };

  const startRecording = async () => {
    if (!question || recorder.recording) return;
    setError(null);
    try {
      await recorder.start(cameraOn, (blob, hasVideo) => void finishRecording(blob, question, hasVideo));
    } catch (reason) { setError({ reason, device: "microphone" }); }
  };

  const chooseQuestion = (index: number) => {
    if (recorder.recording) recorder.stop();
    setActive(index); recorder.setSeconds(0); setMode("record");
  };

  const backToBank = () => {
    if (recorder.recording) recorder.stop();
    setMode("bank");
  };

  // 清掉当前题的转写和录音，准备重录
  const resetAnswer = () => {
    if (!question) return;
    recorder.setSeconds(0);
    setTranscripts((current) => { const next = { ...current }; delete next[question.id]; return next; });
    setRecordings((current) => {
      const next = { ...current };
      if (next[question.id]) URL.revokeObjectURL(next[question.id].url);
      delete next[question.id];
      return next;
    });
  };

  const transcript = question ? transcripts[question.id] ?? "" : "";
  const stats = useMemo(() => wordStats(transcript, recorder.seconds), [recorder.seconds, transcript]);

  return {
    recorder, targets, selectedJobId, setSelectedJobId, selectedTarget, sample, mode, active,
    loading, sampling, transcribing, cameraOn, setCameraOn, transcripts, setTranscripts, recordings, error,
    questions, question, answeredCount, transcript, stats,
    loadQuestions, startRecording, chooseQuestion, backToBank, resetAnswer,
  };
}

export type InterviewSession = ReturnType<typeof useInterviewSession>;
