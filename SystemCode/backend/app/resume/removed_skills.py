"""找出技能栏改写后被删掉的技能，提醒用户确认。

技能栏原文常用缩写或别名（K8s / Kubernetes、Postgres / PostgreSQL），字符串匹配会漏判，
所以交给 LLM 做别名匹配；LLM 输出不合法时退回字符串匹配。
"""

import json
import re

from pydantic import BaseModel, ValidationError

from app.schemas.resume import SkillGroup
from app.services.openai_client_service import ChatClient

# prompt 用英文写，与 llm_resume_parser 一致
SYSTEM_PROMPT = """You compare two versions of a resume's skills section. List every skill, tool, technology or knowledge area that appears in BEFORE but not in AFTER.

Rules:
1. Treat aliases, abbreviations, translations and spelling variants as the same skill (e.g. "K8s" = "Kubernetes", "Postgres" = "PostgreSQL", "JS" = "JavaScript"). A skill that is only reworded or moved to another group is NOT removed.
2. Write each removed skill exactly as BEFORE writes it. Never list skills that appear only in AFTER.
3. Output raw JSON only: {"removed_skills": ["string"]}"""


class _RemovedSkills(BaseModel):
    removed_skills: list[str]


def find_removed_skills(
    client: ChatClient,
    before: list[SkillGroup],
    after: list[SkillGroup],
    skills: list[str],
) -> list[str]:
    old_text = groups_text(before)
    user_prompt = json.dumps(
        {"BEFORE": [g.model_dump() for g in before], "AFTER": [g.model_dump() for g in after]},
        ensure_ascii=False,
    )
    try:
        reported = _RemovedSkills.model_validate_json(
            client.complete(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)
        ).removed_skills
    except ValidationError:
        # ponytail: 退回字符串匹配，只能查出和 skills 列表写法一致的技能
        new_text = groups_text(after)
        return [skill for skill in skills if mentions(old_text, skill) and not mentions(new_text, skill)]

    # 只保留原技能栏或 skills 列表里确实有的名字，防止 LLM 编出原简历没有的技能
    known = {skill.casefold() for skill in skills}
    return list(dict.fromkeys(
        skill for skill in reported if mentions(old_text, skill) or skill.casefold() in known
    ))


def groups_text(groups: list[SkillGroup]) -> str:
    return "\n".join(f"{group.category or ''}: {group.description}" for group in groups)


def mentions(text: str, skill: str) -> bool:
    # 词边界写法与 text_parser.find_skill_matches 一致，避免 "Java" 命中 "JavaScript"
    return re.search(rf"(?<![\w+#]){re.escape(_norm(skill))}(?![\w+#])", _norm(text)) is not None


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()
