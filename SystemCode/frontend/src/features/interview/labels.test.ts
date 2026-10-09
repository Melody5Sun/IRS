import { describe, expect, it } from "vitest";
import type { InterviewQuestion } from "../../types/api";
import { answerText, formatClock, questionText, wordStats } from "./labels";

const question = (overrides: Partial<InterviewQuestion>): InterviewQuestion => ({
  sequence: 1, id: 1, question_type: "role_specific", allocated_role: "Backend Developer",
  question_text: "什么是进程？", standard_answer: "进程是…", question_text_en: "What is a process?", standard_answer_en: "A process is…",
  difficulty_level: "easy", roles: [], source: "test", company: null,
  ...overrides,
});

describe("interview labels", () => {
  it("formats the answer clock", () => {
    expect(formatClock(0)).toBe("00:00");
    expect(formatClock(125)).toBe("02:05");
  });

  it("computes speech rate and filler words", () => {
    expect(wordStats("", 30)).toEqual({ wpm: 0, fillers: 0 });
    expect(wordStats("um I think, like, uh yes", 60)).toEqual({ wpm: 6, fillers: 3 });
  });

  it("shows the Chinese fields in zh and falls back when a language is missing", () => {
    expect(questionText(question({}), "zh")).toBe("什么是进程？");
    expect(questionText(question({}), "en")).toBe("What is a process?");
    expect(questionText(question({ question_text_en: "" }), "en")).toBe("什么是进程？");
    expect(answerText(question({ standard_answer: "" }), "zh")).toBe("A process is…");
  });
});
