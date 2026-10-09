import type { DeletionSuggestion, ResumeDocument, ResumeRewriteResult, RewriteSection } from "../../types/api";

export type Review = "accepted" | "rejected";

// 段落 → 简历上的列表字段；技能栏的 skill_groups 直接在简历根上（与后端 rewrite_applier._TARGETS 一致）
const LIST_KEYS = { experience: "experiences", project: "projects", research: "research" } as const;
// 删除建议按行删时作用的文本字段
const TEXT_FIELDS = { experience: "description", project: "summary", research: "summary" } as const;

type Entry = Record<string, unknown>;

export const blockKey = (block: { section: RewriteSection; index: number }) => `${block.section}:${block.index}`;
export const draftKey = (block: { section: RewriteSection; index: number }, changeIndex: number) => `${blockKey(block)}:${changeIndex}`;

function entries(resume: ResumeDocument, section: keyof typeof LIST_KEYS) {
  return resume[LIST_KEYS[section]] as unknown as Entry[];
}

/**
 * 按用户的审阅结果组装终稿：
 * - 从 rewritten_resume 出发（rewritten 改动已应用，needs_input 字段仍是原文）
 * - 接受的块写入编辑/补全后的值（drafts 里没有就用改写稿原值），其余块写回原文
 * - 再应用用户确认的删除建议
 */
export function buildFinalResume(
  result: ResumeRewriteResult,
  reviews: Record<string, Review>,
  drafts: Record<string, string>,
  deletions: DeletionSuggestion[],
): ResumeDocument {
  const resume = structuredClone(result.rewritten_resume);

  for (const block of result.blocks) {
    const accepted = reviews[blockKey(block)] === "accepted";
    block.changes.forEach((change, changeIndex) => {
      const entry: Entry = change.section === "skills" ? resume : entries(resume, change.section)[change.index];
      entry[change.field] = accepted ? drafts[draftKey(block, changeIndex)] ?? change.value : change.original;
    });
  }

  // 行号对应的是改写前的原文，所以按行的内容查找；这一行已被改写、找不到时跳过
  for (const deletion of deletions) {
    if (deletion.line === null) continue;
    const entry = entries(resume, deletion.section)[deletion.index];
    const field = TEXT_FIELDS[deletion.section];
    const lines = String(entry[field] ?? "").split("\n");
    const at = lines.findIndex((line) => line.trim() === deletion.original.trim());
    if (at >= 0) { lines.splice(at, 1); entry[field] = lines.join("\n"); }
  }

  // 整条删除最后做，同一段落内按下标从大到小删，避免下标错位
  const whole = deletions.filter((deletion) => deletion.line === null);
  for (const section of Object.keys(LIST_KEYS) as Array<keyof typeof LIST_KEYS>) {
    const indexes = [...new Set(whole.filter((deletion) => deletion.section === section).map((deletion) => deletion.index))];
    for (const index of indexes.sort((a, b) => b - a)) entries(resume, section).splice(index, 1);
  }
  return resume;
}
