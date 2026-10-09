import type { Lang, Translate } from "../../i18n/LanguageProvider";
import type { InterviewQuestion } from "../../types/api";

export function typeLabel(value: InterviewQuestion["question_type"], t: Translate) {
  return value === "basic_programming" ? t("interview.type.basic") : t("interview.type.role");
}

export function difficultyLabel(value: InterviewQuestion["difficulty_level"], t: Translate) {
  const keys = { easy: "interview.difficulty.easy", medium: "interview.difficulty.medium", hard: "interview.difficulty.hard", not_stated: "interview.difficulty.notStated" } as const;
  return t(keys[value]);
}

// 题库里 question_text / standard_answer 是中文，*_en 是英文；当前语言的字段为空时回落到另一种
export function questionText(question: InterviewQuestion, lang: Lang) {
  return lang === "zh" ? question.question_text || question.question_text_en : question.question_text_en || question.question_text;
}

export function answerText(question: InterviewQuestion, lang: Lang) {
  return lang === "zh" ? question.standard_answer || question.standard_answer_en : question.standard_answer_en || question.standard_answer;
}

export function formatClock(seconds: number) {
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

// 英文转写的语速（词/分钟）与口头禅次数
export function wordStats(transcript: string, seconds: number) {
  const words = transcript.trim() ? transcript.trim().split(/\s+/) : [];
  const fillers = words.filter((word) => /^(um+|uh+|erm+|like)$/i.test(word.replace(/[^a-z]/gi, ""))).length;
  return { wpm: seconds > 0 ? Math.round(words.length * 60 / seconds) : 0, fillers };
}
