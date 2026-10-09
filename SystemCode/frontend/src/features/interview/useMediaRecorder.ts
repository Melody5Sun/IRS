import { useEffect, useRef, useState } from "react";

// 摄像头/麦克风流、MediaRecorder 与答题计时
export function useMediaRecorder() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);

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

  // 授权失败时直接抛出，由调用方展示错误
  const start = async (withVideo: boolean, onFinish: (blob: Blob, hasVideo: boolean) => void) => {
    setSeconds(0); chunksRef.current = [];
    const stream = await ensureStream(withVideo);
    const hasVideo = withVideo && stream.getVideoTracks().length > 0;
    const recordingStream = hasVideo ? stream : new MediaStream(stream.getAudioTracks());
    const mimeType = hasVideo ? "video/webm" : "audio/webm";
    const recorder = new MediaRecorder(recordingStream, MediaRecorder.isTypeSupported(mimeType) ? { mimeType } : undefined);
    recorderRef.current = recorder;
    recorder.ondataavailable = (event) => { if (event.data.size) chunksRef.current.push(event.data); };
    recorder.onstop = () => onFinish(new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" }), hasVideo);
    recorder.start(); setRecording(true);
    timerRef.current = setInterval(() => setSeconds((value) => value + 1), 1000);
  };

  const stop = () => {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
    setRecording(false);
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
  };

  useEffect(() => () => {
    stopStream();
    if (timerRef.current) clearInterval(timerRef.current);
  }, []);

  return { videoRef, recording, seconds, setSeconds, ensureStream, stopStream, start, stop };
}
