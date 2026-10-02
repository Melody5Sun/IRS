"""把 LLM 输出的 diff 应用到原简历上（参考 srbhr/Resume-Matcher 的 diff-based improvement 设计）。

LLM 只输出要改的地方，原简历由代码保留；每条改动先过本地检查（不调用 LLM），
不通过的单独拒绝并说明原因，通过的才写进改写后的简历。技能栏允许删技能，
删掉了哪些由 removed_skills 调 LLM 做别名匹配找出，放进技能栏块提醒用户。
"""

import re

from app.parsers.text_parser import extract_skills
from app.resume.removed_skills import find_removed_skills, groups_text
from app.schemas.resume import ResumeDocument, SkillGroup
from app.schemas.resume_rewrite import (
    RejectedChange,
    RejectionReason,
    ResumeChange,
    ResumeRewriteResult,
    RewriteBlock,
)
from app.services.openai_client_service import ChatClient, OpenAICompatibleClient


# (段落, 字段) 白名单 → ResumeDocument 上的列表字段名；None 表示字段直接在简历根上（skill_groups）
_TARGETS: dict[tuple[str, str], str | None] = {
    ("experience", "description"): "experiences",
    ("project", "summary"): "projects",
    ("project", "technologies"): "projects",
    ("research", "summary"): "research",
    ("skills", "skill_groups"): None,
}
# 只允许重新排序、不允许增删的列表字段
_REORDER_FIELDS = {"technologies"}

# 篇幅上限：不超过原文 1.8 倍，原文很短时至少允许多 10 个词（参考 Resume-Matcher 的 1.8 倍阈值）
MAX_LENGTH_RATIO = 1.8
MIN_EXTRA_WORDS = 10

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def apply_changes(
    original: ResumeDocument,
    changes: list[ResumeChange],
    jd_company: str,
    client: ChatClient | None = None,
) -> ResumeRewriteResult:
    rewritten = original.model_copy(deep=True)
    resume_skills = _resume_skills(original)
    applied: dict[tuple[str, int], list[ResumeChange]] = {}
    rejected: list[RejectedChange] = []
    seen: set[tuple[str, int, str]] = set()
    removed_skills: list[str] = []

    for change in changes:
        rejection = _check(original, change, seen, resume_skills, jd_company)
        if rejection:
            reason, detail = rejection
            rejected.append(RejectedChange(change=change, reason=reason, detail=detail))
            continue
        seen.add((change.section, change.index, change.field))
        setattr(_entry(rewritten, change), change.field, change.value)
        applied.setdefault((change.section, change.index), []).append(change)
        if change.field == "skill_groups":
            removed_skills = find_removed_skills(
                client or OpenAICompatibleClient(), original.skill_groups, change.value, original.skills
            )

    return ResumeRewriteResult(
        blocks=_blocks(original, applied, removed_skills),
        rewritten_resume=rewritten,
        rejected_changes=rejected,
    )


def _check(
    original: ResumeDocument,
    change: ResumeChange,
    seen: set[tuple[str, int, str]],
    resume_skills: set[str],
    jd_company: str,
) -> tuple[RejectionReason, str] | None:
    target = (change.section, change.field)
    if target not in _TARGETS:
        return "invalid_target", f"{change.section}.{change.field} 不允许改动"
    attr = _TARGETS[target]
    size = 1 if attr is None else len(getattr(original, attr))
    if change.index >= size:
        return "invalid_target", f"{change.section}[{change.index}] 不存在"
    if (change.section, change.index, change.field) in seen:
        return "invalid_target", "同一字段被改了两次，只保留第一次"

    if change.field == "skill_groups":
        return _check_skill_groups(original, change, resume_skills, jd_company)

    current = getattr(_entry(original, change), change.field)

    if change.field in _REORDER_FIELDS:
        if not isinstance(change.original, list) or not isinstance(change.value, list):
            return "invalid_target", f"{change.field} 的原文和新值都必须是列表"
        if _norm_list(change.original) != _norm_list(current):
            return "original_mismatch", "复述的原列表与简历不一致"
        if sorted(_norm_list(change.value)) != sorted(_norm_list(current)):
            return "not_a_reorder", f"{change.field} 只能调整顺序，不能增删条目"
        return None

    if not isinstance(change.original, str) or not isinstance(change.value, str):
        return "invalid_target", f"{change.field} 的原文和新值都必须是字符串"
    if _norm(change.original) != _norm(current):
        return "original_mismatch", "复述的原文与简历不一致"

    old_words = len(current.split())
    limit = max(old_words * MAX_LENGTH_RATIO, old_words + MIN_EXTRA_WORDS)
    if len(change.value.split()) > limit:
        return "too_long", f"改写后 {len(change.value.split())} 词，超过上限 {int(limit)} 词"

    return _check_facts(current, change.value, current, resume_skills, jd_company)


def _check_skill_groups(
    original: ResumeDocument,
    change: ResumeChange,
    resume_skills: set[str],
    jd_company: str,
) -> tuple[RejectionReason, str] | None:
    """技能栏整体改写：输出完整的新 skill_groups，可补入 skills 列表里有、原技能栏没写的技能；删技能不拒绝，由调用方提醒用户。"""
    if not all(
        isinstance(groups, list) and all(isinstance(group, SkillGroup) for group in groups)
        for groups in (change.original, change.value)
    ):
        return "invalid_target", "skill_groups 的原文和新值都必须是技能分组列表"
    if _groups_key(change.original) != _groups_key(original.skill_groups):
        return "original_mismatch", "复述的原技能栏与简历不一致"

    old_text = groups_text(original.skill_groups)
    new_text = groups_text(change.value)
    # skills 列表里的技能允许补进技能栏，它们自带的数字（如 "Vue 3"）也算有依据
    evidence = "\n".join([old_text, *original.skills])
    # 分类名（"Databases"、"Cloud" 等）会命中技能词表别名，新技能检查只看各组的技能描述
    descriptions = "\n".join(group.description for group in change.value)
    return _check_facts(old_text, new_text, evidence, resume_skills, jd_company, skill_text=descriptions)


def _check_facts(
    current: str,
    value: str,
    evidence: str,
    resume_skills: set[str],
    jd_company: str,
    skill_text: str | None = None,
) -> tuple[RejectionReason, str] | None:
    """文本改写共用的事实检查：不能出现依据里没有的数字、原简历没有的技能、目标公司名。

    skill_text 不为空时只在这段文本里查新技能（技能栏用它排除分类名），数字和公司名仍查整个 value。
    """
    new_numbers = set(_NUMBER.findall(value)) - set(_NUMBER.findall(evidence))
    if new_numbers:
        return "new_number", f"原文中没有这些数字：{sorted(new_numbers)}"

    # ponytail: 只能识别技能词表里的技能，词表外的新技术名词查不出来；接入 MIND 图谱后可扩大覆盖
    new_skills = set(extract_skills(value if skill_text is None else skill_text)) - resume_skills
    if new_skills:
        return "new_skill", f"原简历中没有这些技能：{sorted(new_skills)}"

    company = _norm(jd_company)
    if company and company in _norm(value) and company not in _norm(current):
        return "jd_company_mention", f"不应把目标公司 {jd_company!r} 写进经历"
    return None


def _entry(resume: ResumeDocument, change: ResumeChange) -> object:
    attr = _TARGETS[(change.section, change.field)]
    return resume if attr is None else getattr(resume, attr)[change.index]


def _resume_skills(resume: ResumeDocument) -> set[str]:
    # 原简历里任何位置提到过的技能都算有依据
    texts = [*resume.skills, groups_text(resume.skill_groups)]
    texts += [item.description for item in resume.experiences]
    for project in resume.projects:
        texts += [project.summary, *project.technologies]
    texts += [item.summary for item in resume.research]
    return set(extract_skills("\n".join(texts)))


def _blocks(
    original: ResumeDocument,
    applied: dict[tuple[str, int], list[ResumeChange]],
    removed_skills: list[str],
) -> list[RewriteBlock]:
    headings = [
        *(("experience", i, f"{item.title} · {item.company}") for i, item in enumerate(original.experiences)),
        *(("project", i, item.title) for i, item in enumerate(original.projects)),
        *(("research", i, item.title) for i, item in enumerate(original.research)),
        ("skills", 0, "Skills"),
    ]
    return [
        RewriteBlock(
            section=section, index=index, heading=heading, changes=applied.get((section, index), []),
            removed_skills=removed_skills if section == "skills" else [],
        )
        for section, index, heading in headings
    ]


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def _norm_list(items: list[str]) -> list[str]:
    return [_norm(item) for item in items]


def _groups_key(groups: list[SkillGroup]) -> list[tuple[str, str]]:
    return [(_norm(group.category or ""), _norm(group.description)) for group in groups]

