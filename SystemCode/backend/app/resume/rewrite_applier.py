"""把 LLM 输出的 diff 应用到原简历上（参考 srbhr/Resume-Matcher 的 diff-based improvement 设计）。

LLM 只输出要改的地方，原简历由代码保留；每条改动先过本地检查（不调用 LLM），
不通过的单独拒绝并说明原因，通过的才写进改写后的简历。
"""

import re

from app.parsers.text_parser import extract_skills
from app.schemas.resume import ResumeDocument
from app.schemas.resume_rewrite import (
    RejectedChange,
    RejectionReason,
    ResumeChange,
    ResumeRewriteResult,
    RewriteBlock,
)


# (段落, 字段) 白名单 → ResumeDocument 上的列表字段名；None 表示字段直接在简历根上（skills）
_TARGETS: dict[tuple[str, str], str | None] = {
    ("experience", "description"): "experiences",
    ("project", "summary"): "projects",
    ("project", "technologies"): "projects",
    ("research", "summary"): "research",
    ("skills", "skills"): None,
}
# 只允许重新排序、不允许增删的列表字段
_REORDER_FIELDS = {"technologies", "skills"}

# 篇幅上限：不超过原文 1.8 倍，原文很短时至少允许多 10 个词（参考 Resume-Matcher 的 1.8 倍阈值）
MAX_LENGTH_RATIO = 1.8
MIN_EXTRA_WORDS = 10

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def apply_changes(
    original: ResumeDocument,
    changes: list[ResumeChange],
    jd_company: str,
) -> ResumeRewriteResult:
    rewritten = original.model_copy(deep=True)
    resume_skills = _resume_skills(original)
    applied: dict[tuple[str, int], list[ResumeChange]] = {}
    rejected: list[RejectedChange] = []
    seen: set[tuple[str, int, str]] = set()

    for change in changes:
        rejection = _check(original, change, seen, resume_skills, jd_company)
        if rejection:
            reason, detail = rejection
            rejected.append(RejectedChange(change=change, reason=reason, detail=detail))
            continue
        seen.add((change.section, change.index, change.field))
        setattr(_entry(rewritten, change), change.field, change.value)
        applied.setdefault((change.section, change.index), []).append(change)

    return ResumeRewriteResult(
        blocks=_blocks(original, applied),
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

    new_numbers = set(_NUMBER.findall(change.value)) - set(_NUMBER.findall(current))
    if new_numbers:
        return "new_number", f"原文中没有这些数字：{sorted(new_numbers)}"

    # ponytail: 只能识别技能词表里的技能，词表外的新技术名词查不出来；接入 MIND 图谱后可扩大覆盖
    new_skills = set(extract_skills(change.value)) - resume_skills
    if new_skills:
        return "new_skill", f"原简历中没有这些技能：{sorted(new_skills)}"

    old_words = len(current.split())
    limit = max(old_words * MAX_LENGTH_RATIO, old_words + MIN_EXTRA_WORDS)
    if len(change.value.split()) > limit:
        return "too_long", f"改写后 {len(change.value.split())} 词，超过上限 {int(limit)} 词"

    company = _norm(jd_company)
    if company and company in _norm(change.value) and company not in _norm(current):
        return "jd_company_mention", f"不应把目标公司 {jd_company!r} 写进经历"
    return None


def _entry(resume: ResumeDocument, change: ResumeChange) -> object:
    attr = _TARGETS[(change.section, change.field)]
    return resume if attr is None else getattr(resume, attr)[change.index]


def _resume_skills(resume: ResumeDocument) -> set[str]:
    # 原简历里任何位置提到过的技能都算有依据
    texts = [*resume.skills]
    texts += [item.description for item in resume.experiences]
    for project in resume.projects:
        texts += [project.summary, *project.technologies]
    texts += [item.summary for item in resume.research]
    return set(extract_skills("\n".join(texts)))


def _blocks(
    original: ResumeDocument,
    applied: dict[tuple[str, int], list[ResumeChange]],
) -> list[RewriteBlock]:
    headings = [
        *(("experience", i, f"{item.title} · {item.company}") for i, item in enumerate(original.experiences)),
        *(("project", i, item.title) for i, item in enumerate(original.projects)),
        *(("research", i, item.title) for i, item in enumerate(original.research)),
        ("skills", 0, "Skills"),
    ]
    return [
        RewriteBlock(section=section, index=index, heading=heading, changes=applied.get((section, index), []))
        for section, index, heading in headings
    ]


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def _norm_list(items: list[str]) -> list[str]:
    return [_norm(item) for item in items]
