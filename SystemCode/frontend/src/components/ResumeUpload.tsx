import { useState } from "react";
import { getResumeHistory, saveParsedResume } from "../lib/profileStorage";
import type { Profile, ResumeDocument } from "../types/profile";

const PARSE_PDF_URL = "http://localhost:8000/api/resumes/parse-pdf";

interface Props {
  onParsed: (profile: Profile) => void;
}

export function ResumeUpload({ onParsed }: Props) {
  const [historyCount, setHistoryCount] = useState(() => getResumeHistory().length);
  const [error, setError] = useState<string | null>(null);

  async function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setError(null);

    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(PARSE_PDF_URL, { method: "POST", body: formData });
    if (!response.ok) {
      setError(`解析失败：${response.status}`);
      return;
    }

    const resume: ResumeDocument = await response.json();
    const saved = saveParsedResume(resume);
    setHistoryCount(getResumeHistory().length);
    onParsed(saved);
  }

  return (
    <div>
      <h2>上传简历（PDF）</h2>
      <input type="file" accept="application/pdf" onChange={handleFileChange} />
      {error && <p style={{ color: "red" }}>{error}</p>}
      <p>localStorage 里的简历解析历史条数：{historyCount}</p>
    </div>
  );
}
