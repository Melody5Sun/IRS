import re

from app.parsers.skill_lexicon import SKILL_SYNONYMS

EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_PATTERN = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
EXPERIENCE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", re.IGNORECASE)
# 转小写后会撞上技能别名的普通写法：ReAct 是 Agent 推理范式不是 React；夹在英文单词之间的小写 go 是动词不是 Go 语言
FALSE_ALIAS_PATTERN = re.compile(r"(?<![\w+#])ReAct(?![\w+#])|(?<=[A-Za-z] )go\b|\bgo(?= [A-Za-z])")


def extract_email(text: str) -> str | None:
    match = EMAIL_PATTERN.search(text)
    return match.group(0) if match else None


def extract_phone(text: str) -> str | None:
    match = PHONE_PATTERN.search(text)
    return match.group(0).strip() if match else None


def extract_experience_years(text: str) -> float | None:
    matches = [float(match.group(1)) for match in EXPERIENCE_PATTERN.finditer(text)]
    return max(matches) if matches else None


def extract_skills(text: str) -> list[str]:
    return [skill for skill, _ in find_skill_matches(text)]


def find_skill_matches(text: str) -> list[tuple[str, str]]:
    normalized_text = FALSE_ALIAS_PATTERN.sub(" ", text).lower()
    matches: dict[str, str] = {}
    for skill, aliases in SKILL_SYNONYMS.items():
        for alias in aliases:
            pattern = rf"(?<![\w+#]){re.escape(alias.lower())}(?![\w+#])"
            if re.search(pattern, normalized_text):
                matches[skill] = alias
                break
    return sorted(matches.items())


def first_non_empty_line(text: str) -> str | None:
    for line in text.splitlines():
        clean_line = line.strip()
        if clean_line:
            return clean_line
    return None
