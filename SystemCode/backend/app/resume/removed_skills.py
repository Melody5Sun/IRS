"""比较技能栏改写前后：删掉了哪些技能（提醒用户确认）、新加了哪些原简历没有的技能（拒绝这条改动）。

技能栏原文常用缩写或别名（K8s / Kubernetes、Postgres / PostgreSQL），字符串匹配会漏判，
所以交给 LLM 做别名匹配；技能词表也认不出 "Data Analysis" 这类词表外的编造技能。
LLM 输出不合法时删除退回字符串匹配，新增只靠调用方的词表检查。
"""

import json
import re

from pydantic import BaseModel, Field, ValidationError

from app.schemas.resume import SkillGroup
from app.services.openai_client_service import ChatClient

# prompt 用英文写，与 llm_resume_parser 一致
SYSTEM_PROMPT = """You compare two versions of a resume's skills section. SKILLS is the full list of skills the candidate already has.
List (a) removed_skills: every skill, tool, technology or knowledge area that appears in BEFORE but not in AFTER, and (b) added_skills: every skill, tool, technology or knowledge area in AFTER that appears in neither BEFORE nor SKILLS.

Rules:
1. Treat aliases, abbreviations, translations and spelling variants as the same skill (e.g. "K8s" = "Kubernetes", "Postgres" = "PostgreSQL", "JS" = "JavaScript"). A skill that is only reworded, regrouped or moved is neither removed nor added. Group names (categories) are not skills.
2. Write each removed skill exactly as BEFORE writes it, and each added skill exactly as AFTER writes it.
3. Output raw JSON only: {"removed_skills": ["string"], "added_skills": ["string"]}"""


class _SkillDiff(BaseModel):
    removed_skills: list[str]
    added_skills: list[str] = Field(default_factory=list)


def compare_skill_groups(
    client: ChatClient,
    before: list[SkillGroup],
    after: list[SkillGroup],
    skills: list[str],
) -> tuple[list[str], list[str]]:
    """返回（删掉的技能, 原简历没有的新增技能）。"""
    old_text = groups_text(before)
    user_prompt = json.dumps(
        {"BEFORE": [g.model_dump() for g in before], "AFTER": [g.model_dump() for g in after], "SKILLS": skills},
        ensure_ascii=False,
    )
    try:
        diff = _SkillDiff.model_validate_json(client.complete(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt))
    except ValidationError:
        # ponytail: 退回字符串匹配，只能查出和 skills 列表写法一致的删除；新增只剩调用方的词表检查
        new_text = groups_text(after)
        return [skill for skill in skills if mentions(old_text, skill) and not mentions(new_text, skill)], []

    # 只保留原技能栏或 skills 列表里确实有的名字，防止 LLM 编出原简历没有的技能
    known = {skill.casefold() for skill in skills}
    removed = list(dict.fromkeys(
        skill for skill in diff.removed_skills if mentions(old_text, skill) or skill.casefold() in known
    ))
    # 新增项若其实在原技能栏或 skills 列表里能直接找到，是 LLM 判断失误，不算编造，避免误拒
    evidence = "\n".join([old_text, *skills])
    added = list(dict.fromkeys(skill for skill in diff.added_skills if not mentions(evidence, skill)))
    return removed, added


def groups_text(groups: list[SkillGroup]) -> str:
    return "\n".join(f"{group.category or ''}: {group.description}" for group in groups)


def mentions(text: str, skill: str) -> bool:
    # 词边界写法与 text_parser.find_skill_matches 一致，避免 "Java" 命中 "JavaScript"
    return re.search(rf"(?<![\w+#]){re.escape(_norm(skill))}(?![\w+#])", _norm(text)) is not None


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()
