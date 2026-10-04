"""简历改写（RAG）：问题检测 → 按问题类型检索知识库 → 单次 LLM 调用输出改动 → 本地检查后应用。

LLM 只输出改动（ResumeChangeSet），原简历由 apply_changes 保留和校验；
删除建议不直接应用，原样返回给前端由用户确认。
信息不足的块（改写稿带占位 + needs_user_input）不直接应用，由 fill_block 和用户多轮问答补全。
"""

import json
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.matching.embedding_provider import EmbeddingProvider, SentenceTransformerEmbeddingProvider
from app.repositories.resume_guideline_repository import GuidelineMatch, ResumeGuidelineRepository
from app.resume.issue_detector import BlockIssues, detect_issues, jd_alignments
from app.parsers.text_parser import extract_skills
from app.resume.rewrite_applier import MIN_EXTRA_WORDS, apply_changes, check_facts, placeholders
from app.schemas.job import JobRequirementDocument
from app.schemas.match import SkillScoreRequest
from app.schemas.resume import ResumeDocument
from app.schemas.resume_guideline import IssueType, ResumeGuideline
from app.schemas.resume_rewrite import (
    BlockFill,
    CitedGuideline,
    DeletionSuggestion,
    PlaceholderAnswer,
    RejectedDeletion,
    ResumeChangeSet,
    ResumeRewriteResult,
    RewriteReason,
)
from app.services.openai_client_service import ChatClient, OpenAICompatibleClient
from app.services.responsibility_match_service import ResponsibilityMatchService
from app.services.skill_match_service import SkillMatchService

# 每个（行, 问题类型）检索的条目数；技能栏每个问题类型检索的条目数
LINE_TOP_K = 1
SKILLS_TOP_K = 2
# 写法类和 JD 关系类问题：向量按主题匹配，用简历原文检索常拿到同主题但不讲这个问题的条目（如弱动词拿到“大数据要写数据量”），
# 所以每块再用问题描述检索一次。7 组简历×岗位上“有对题条目”的比例 16/39 → 35/39（剩下的是研究经历块，知识库缺对应条目）
ISSUE_QUERIES: dict[str, str] = {
    "weak_action_verb": "Bullet opens with 'Responsible for', 'Participated in' or 'Helped' instead of a strong past-tense action verb.",
    "passive_voice": "Passive voice such as 'was developed' or 'were implemented by me' hides who did the work.",
    "buzzword": "Buzzwords and filler such as 'leveraged', 'cutting-edge', 'innovative' or 'successfully' instead of concrete facts.",
    "irrelevant_content": "Experience or project that does not match the target role: shorten it to one line of transferable skills, move it down, or drop it.",
    "weak_jd_alignment": "Align the entry with the job description: put the job-relevant work first and use the job's terminology.",
}
# 经历/项目/研究块：可改写的文本字段、在 ResumeDocument 上的列表名
TEXT_FIELD = {"experience": "description", "project": "summary", "research": "summary"}
LIST_ATTR = {"experience": "experiences", "project": "projects", "research": "research"}

# prompt 用英文写，与 llm_resume_parser 一致
SYSTEM_PROMPT = """You are an expert technical resume editor for IT students. You receive a resume split into BLOCKS, the target JOB, and for each block the detected ISSUES plus GUIDELINES retrieved from an expert knowledge base, grouped by issue type. Improve the blocks so they fix the issues and align with the job, following the guidelines. Output raw JSON only.

Output schema:
{
  "changes": [{
    "section": "experience|project|research|skills",
    "index": 0,                       // the block's index
    "field": "description|summary|technologies|skill_groups",
    "original": ...,                  // the CURRENT value of that field, copied verbatim
    "value": ...,                     // the new value, same type as original
    "reasons": [{
      "issue_type": "<one of the block's issue types>",
      "explanation": {"en": "...", "zh": "..."},
      "guideline_keys": ["<key>"],
      "jd_responsibility": "<the job responsibility this change aligns to, verbatim, or null>"
    }],
    "needs_user_input": [{
      "placeholder": "[...]",          // exactly as it appears in value
      "question": {"en": "...", "zh": "..."},
      "reason": {"en": "...", "zh": "..."}
    }]
  }],
  "deletions": [{
    "section": "experience|project|research",
    "index": 0,
    "line": null,                     // null = delete the whole entry; a number = delete that line of the text (0-based, split on "\\n")
    "original": "...",                // the whole text, or that line, copied verbatim
    "reasons": [ same shape as above ]
  }]
}

Editable fields (anything else will be rejected): experience -> "description"; project -> "summary" or "technologies"; research -> "summary"; skills (index 0) -> "skill_groups". Change each field at most once.

Rules:
1. No fabrication. Use only facts already in the block. Never add numbers, percentages, durations or scale that are not in the original; never add a skill, tool or technology that this block (its text or its technologies list) does not already mention; never mention the job's company. Never upgrade the strength of a contribution: "participated in", "assisted" or "helped" may become "contributed to" or "co-designed", never "led", "owned" or "spearheaded". For "unclear_tech_stack", surface only technologies this block already names; if none fit, write a placeholder such as "[framework/tool used]" and ask the user. When a guideline asks for data the block does not contain (a metric, an outcome, a scale), write a short bracketed placeholder such as "[number of users]" in value and add a needs_user_input item with the same placeholder, a question for the user and why it matters. Every new placeholder in value must have exactly one needs_user_input item and every needs_user_input item must have its placeholder in value; otherwise the change is rejected. Use placeholders only for information the block really lacks.
2. Copy "original" exactly (same wording and line breaks). Keep one bullet per line joined with "\\n", keep the same bullets in the same order unless merging is clearly better, and keep value at most 1.8 times the length of the original.
3. "technologies": only reorder the existing items by relevance to the job; never add or remove items.
4. "skill_groups" (value is the complete new skills section as [{"category": "string|null", "description": "string"}]): consider both SKILLS and the original skill_groups; keep only skills useful for the job, ordered by importance to the job (groups and skills inside each group); you may add skills that are in SKILLS but missing from the original skill_groups; you may drop irrelevant skills.
5. Only change blocks that have issues, and only to fix them. Write the resume text in English.
6. reasons: every change needs at least one reason. explanation is 1-2 plain sentences addressed to the student: what is weak in THIS text, what the cited guideline recommends, and WHY, by paraphrasing that guideline's rationale in your own words (do not copy it and do not write guideline keys in it). Write it in English (en) and Simplified Chinese (zh). guideline_keys may only contain keys listed in that block's guidelines under the same issue type as the reason.
7. deletions: only for blocks whose issues include "irrelevant_content". Suggest deleting the whole entry, or single lines that do not support the job. Do not also rewrite an entry you suggest deleting entirely. The user confirms every deletion, so explain why in reasons.
8. If nothing needs to change, return {"changes": [], "deletions": []}."""


FILL_SYSTEM_PROMPT = """You finish one resume block for an IT student. You receive the block TEXT (it contains bracketed placeholders such as "[number of users]" where data was missing), the target JOB, and the student's ANSWERS for some placeholders. Output raw JSON only:
{"value": "...", "needs_user_input": [{"placeholder": "[...]", "question": {"en": "...", "zh": "..."}, "reason": {"en": "...", "zh": "..."}}]}

Rules:
1. For each answered placeholder, rewrite the sentence so the answer reads naturally in place of the placeholder (fix grammar and wording; do not just paste it in).
2. For each placeholder whose answer is null (the student skipped it), remove the placeholder and rephrase that sentence neutrally without the missing information. Do not guess a value.
3. Placeholders that are not in ANSWERS stay exactly as they are.
4. Use only facts from TEXT and ANSWERS. Never add numbers, skills, tools, scale or outcomes that are not there, and never mention the job's company. Keep everything else unchanged: same bullets, same order, one bullet per line joined with "\\n". Write in English.
5. If an answer is too vague to state as a fact (e.g. "a lot", "not sure", "it improved"), keep a placeholder for it in value and add a needs_user_input item with that placeholder: a specific follow-up question and why it matters, in English (en) and Simplified Chinese (zh). Otherwise needs_user_input is []."""

_T = TypeVar("_T", bound=BaseModel)


class ResumeRewriteError(RuntimeError):
    """LLM 两次尝试后仍未能返回合法（JSON 合法且通过本地检查）的输出。"""


class ResumeRewriter:
    def __init__(
        self,
        client: ChatClient | None = None,
        guideline_repository: ResumeGuidelineRepository | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        responsibility_service: ResponsibilityMatchService | None = None,
        skill_service: SkillMatchService | None = None,
    ) -> None:
        self.client = client or OpenAICompatibleClient()
        self.guideline_repository = guideline_repository or ResumeGuidelineRepository()
        self.embedding_provider = embedding_provider or SentenceTransformerEmbeddingProvider(
            settings.resume_guideline_embedding_model
        )
        self.responsibility_service = responsibility_service or ResponsibilityMatchService()
        self.skill_service = skill_service or SkillMatchService()

    def rewrite(
        self,
        resume: ResumeDocument,
        job: JobRequirementDocument,
        role_categories: list[str],
    ) -> ResumeRewriteResult:
        scorer = self.responsibility_service.scorer
        blocks = detect_issues(
            resume,
            jd_alignments(self.responsibility_service, resume, job),
            self.skill_service.score(SkillScoreRequest(candidate=resume, job=job)),
            scorer.similarity_floor,
            scorer.similarity_full,
        )
        # 技能栏没有分组原文时无从改写；其余块只把有问题的交给 LLM
        blocks = [b for b in blocks if (b.has_issues if b.section != "skills" else bool(resume.skill_groups))]
        retrieved = self._retrieve(blocks, role_categories)
        guidelines = {
            m.guideline.key: m.guideline
            for by_issue in retrieved.values() for matches in by_issue.values() for m in matches
        }

        change_set = self._complete_json(
            SYSTEM_PROMPT, self._user_prompt(resume, job, blocks, retrieved), ResumeChangeSet
        )
        for item in [*change_set.changes, *change_set.deletions]:
            _keep_known_keys(item.reasons, retrieved.get((item.section, item.index), {}))

        result = apply_changes(resume, change_set.changes, jd_company=job.company, client=self.client)
        irrelevant = {(b.section, b.index) for b in blocks if "irrelevant_content" in b.block_issues}
        for deletion in change_set.deletions:
            if detail := _check_deletion(resume, deletion, irrelevant):
                result.rejected_deletions.append(RejectedDeletion(deletion=deletion, detail=detail))
            else:
                result.deletion_suggestions.append(deletion)

        result.job_id = job.job_id
        result.guidelines = _cited(change_set, guidelines)
        return result

    def fill_block(
        self,
        text: str,
        answers: list[PlaceholderAnswer],
        job: JobRequirementDocument,
        technologies: list[str],
    ) -> BlockFill:
        """待补充块的一轮问答：把用户回答写进草稿、跳过的改成中性表述，回答含糊时追问。
        不再检索知识库：写法指导首轮已经用过，这一步只融合用户提供的事实。"""
        answered = [a.answer.strip() for a in answers if a.answer and a.answer.strip()]
        evidence = "\n".join([text, *answered])
        known_skills = set(extract_skills("\n".join([evidence, *technologies])))
        handled = {a.placeholder for a in answers}
        limit = len(text.split()) + len(" ".join(answered).split()) + MIN_EXTRA_WORDS

        def check(fill: BlockFill) -> str | None:
            asked = {item.placeholder for item in fill.needs_user_input}
            if extra := placeholders(fill.value) - (placeholders(text) - handled) - asked:
                return f"value 里的占位 {sorted(extra)} 既不是未回答的原占位，也没有在 needs_user_input 里追问"
            if missing := asked - placeholders(fill.value):
                return f"needs_user_input 的占位 {sorted(missing)} 没有出现在 value 里"
            if len(fill.value.split()) > limit:
                return f"改写后 {len(fill.value.split())} 词，超过上限 {limit} 词"
            if rejection := check_facts(text, fill.value, evidence, known_skills, job.company):
                return rejection[1]
            return None

        user_prompt = json.dumps(
            {
                "JOB": {"title": job.title, "company": job.company},
                "TEXT": text,
                "ANSWERS": [
                    {"placeholder": a.placeholder, "answer": (a.answer or "").strip() or None} for a in answers
                ],
            },
            ensure_ascii=False,
        )
        return self._complete_json(FILL_SYSTEM_PROMPT, user_prompt, BlockFill, check)

    def _retrieve(
        self, blocks: list[BlockIssues], role_categories: list[str]
    ) -> dict[tuple[str, int], dict[str, list[GuidelineMatch]]]:
        """每个（行, 问题类型）单独检索：一次检索只带一个问题类型，写法类问题（被动语态、空话）的条目
        才不会被主题相近的条目挤掉；块级问题和技能栏用整块文本作 query。结果按 块 → 问题类型 → 条目 组织。"""
        queries: list[tuple[BlockIssues, str, IssueType, int]] = []
        for block in blocks:
            if block.section == "skills":
                queries += [(block, block.text or "skills", issue, SKILLS_TOP_K) for issue in block.block_issues]
                continue
            queries += [(block, line.text, issue, LINE_TOP_K) for line in block.lines for issue in line.issue_types]
            queries += [(block, block.text, issue, LINE_TOP_K) for issue in block.block_issues]
            issues = {i for line in block.lines for i in line.issue_types} | set(block.block_issues)
            queries += [(block, ISSUE_QUERIES[issue], issue, LINE_TOP_K) for issue in sorted(issues) if issue in ISSUE_QUERIES]

        embeddings = self.embedding_provider.encode([text for _, text, _, _ in queries])
        found: dict[tuple[str, int], dict[str, dict[str, GuidelineMatch]]] = {(b.section, b.index): {} for b in blocks}
        for (block, _, issue, top_k), embedding in zip(queries, embeddings, strict=True):
            matches = self.guideline_repository.search(
                embedding,
                model_name=settings.resume_guideline_embedding_model,
                sections=[block.section],
                issue_types=[issue],
                role_categories=role_categories,
                top_k=top_k,
            )
            bucket = found[(block.section, block.index)].setdefault(issue, {})
            for match in matches:
                if match.guideline.key not in bucket or match.similarity > bucket[match.guideline.key].similarity:
                    bucket[match.guideline.key] = match
        return {
            key: {
                issue: sorted(bucket.values(), key=lambda m: m.similarity, reverse=True)
                for issue, bucket in by_issue.items()
            }
            for key, by_issue in found.items()
        }

    @staticmethod
    def _user_prompt(
        resume: ResumeDocument,
        job: JobRequirementDocument,
        blocks: list[BlockIssues],
        retrieved: dict[tuple[str, int], dict[str, list[GuidelineMatch]]],
    ) -> str:
        payload_blocks = []
        for block in blocks:
            item: dict[str, object] = {"section": block.section, "index": block.index, "heading": block.heading}
            if block.section == "skills":
                item["skill_groups"] = [group.model_dump() for group in resume.skill_groups]
                item["SKILLS"] = resume.skills
                item["skills_required_by_job_but_not_shown_in_experience"] = block.unsurfaced_skills
            else:
                item["field"] = TEXT_FIELD[block.section]
                item["text"] = block.text
                if block.section == "project":
                    item["technologies"] = resume.projects[block.index].technologies
                item["line_issues"] = [
                    {"line": line.line, "text": line.text, "issues": line.issue_types} for line in block.lines
                ]
                item["aligned_job_responsibility"] = block.jd_responsibility
            item["block_issues"] = block.block_issues
            # 按问题类型分组，LLM 写某个 issue_type 的理由时只能引用该组下的条目
            item["guidelines"] = {
                issue: [_guideline_payload(match) for match in matches]
                for issue, matches in retrieved[(block.section, block.index)].items()
            }
            payload_blocks.append(item)
        return json.dumps(
            {
                "JOB": {
                    "title": job.title,
                    "company": job.company,
                    "summary": job.summary,
                    "responsibilities": job.responsibilities,
                    "required_skills": job.required_skills,
                    "preferred_skills": job.preferred_skills,
                },
                "BLOCKS": payload_blocks,
            },
            ensure_ascii=False,
        )

    def _complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        model: type[_T],
        check: Callable[[_T], str | None] | None = None,
    ) -> _T:
        """最多调两次 LLM：输出不是合法 JSON，或没通过 check（返回错误说明），就带上错误重试一次。"""
        prompt = user_prompt
        error = ""
        for _ in range(2):
            raw = self.client.complete(system_prompt=system_prompt, user_prompt=prompt)
            try:
                result = model.model_validate_json(raw)
            except (json.JSONDecodeError, ValidationError) as validation_error:
                error = str(validation_error)
            else:
                if (error := check(result) if check else None) is None:
                    return result
            prompt = (
                f"{user_prompt}\n\n"
                f"上一次的输出没有通过校验，错误信息：{error}\n"
                "请重新只输出一个符合 schema 的 JSON 对象。"
            )
        raise ResumeRewriteError(f"LLM 重试后仍未能返回合法的输出：{error}")


def _guideline_payload(match: GuidelineMatch) -> dict[str, object]:
    guideline = match.guideline
    # 示例优先用检索命中的那一个（改写前原句和用户原句最像）
    example = next((e for e in guideline.examples if e.before == match.matched_chunk_text), guideline.examples[0])
    return {
        "key": guideline.key,
        "title": guideline.title,
        "guideline": guideline.guideline,
        "rationale": guideline.rationale,
        "example": example.model_dump(),
    }


def _keep_known_keys(reasons: list[RewriteReason], retrieved: dict[str, list[GuidelineMatch]]) -> None:
    # 防止编造或错配引用：只保留本块在该理由的问题类型下确实检索到的条目
    for reason in reasons:
        allowed = {match.guideline.key for match in retrieved.get(reason.issue_type, [])}
        reason.guideline_keys = [key for key in reason.guideline_keys if key in allowed]


def _check_deletion(
    resume: ResumeDocument, deletion: DeletionSuggestion, irrelevant: set[tuple[str, int]]
) -> str | None:
    if (deletion.section, deletion.index) not in irrelevant:
        return "该条目与 JD 有一定相关性，不建议删除"
    entries = getattr(resume, LIST_ATTR[deletion.section])
    if deletion.index >= len(entries):
        return f"{deletion.section}[{deletion.index}] 不存在"
    text = getattr(entries[deletion.index], TEXT_FIELD[deletion.section])
    if deletion.line is None:
        current = text
    else:
        lines = text.split("\n")
        if deletion.line >= len(lines):
            return f"第 {deletion.line} 行不存在"
        current = lines[deletion.line]
    if _norm(deletion.original) != _norm(current):
        return "复述的原文与简历不一致"
    return None


def _cited(change_set: ResumeChangeSet, guidelines: dict[str, ResumeGuideline]) -> list[CitedGuideline]:
    keys = dict.fromkeys(
        key
        for item in [*change_set.changes, *change_set.deletions]
        for reason in item.reasons
        for key in reason.guideline_keys
    )
    return [
        CitedGuideline(key=key, title=g.title, source=g.source, source_url=g.source_url)
        for key in keys
        if (g := guidelines.get(key))
    ]


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()
