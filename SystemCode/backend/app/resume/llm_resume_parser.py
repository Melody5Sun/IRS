import json
import re
from typing import Any

from pydantic import ValidationError

from app.schemas.resume import ParsedResume
from app.services.openai_client_service import ChatClient, OpenAICompatibleClient

# prompt 用英文写：输出必须是英文，中文指令容易让模型把中文带进 JSON 值里
SYSTEM_PROMPT = """You are a resume parser. Convert the resume text into ONE JSON object following the schema below. Output raw JSON only: no markdown, no comments, no extra text.

Rules:
1. No fabrication: use only what the resume states. If absent or unclear: "string|null" -> null, list -> [], employment_type -> null, degree -> "not_applicable", required "string" -> "".
2. Be complete: read every section; keep every entry and every bullet point (tools, numbers, outcomes) without merging or shortening. Each item goes in exactly one section.
3. English only: every human-readable string value must be in English and contain no Chinese characters. Translate non-English text faithfully; use an organization's official English name, otherwise romanize it. Do not preserve the original Chinese text in parentheses. Keep emails, phones and URLs unchanged.
4. Dates: "YYYY-MM", or "YYYY" if only the year is given. Ongoing -> end_date "present"; expected graduation -> that date.
5. Keep everything: use only schema keys, but never drop resume content. Content with no dedicated field goes into additional_info as "Label: value" (e.g. "Age: 22", "Hobbies: hiking").

Schema (// explains the field):
{
  "name": "string|null", "email": "string|null", "phone": "string|null",
  "about": "string|null",  // the resume's own summary/objective; never write one
  "experiences": [{  // employment: internship, full-time, part-time, contract, freelance
    "company": "string", "title": "string",
    "employment_type": "full_time|part_time|internship|null",  // explicit wording only; a plain job title -> null; any other stated type (e.g. contract, freelance) -> null and record it in additional_info as "Employment type at <company>: <type>"
    "start_date": "string|null", "end_date": "string|null",
    "description": "string",  // all bullet points, joined with "\\n"
    "country": "string|null"  // country of the stated work location
  }],
  "projects": [{  // personal, course, hackathon, open-source
    "title": "string",
    "summary": "string",  // what was built, how, results; all bullet points
    "technologies": ["string"],  // named for this project
    "role": "string|null",
    "start_date": "string|null", "end_date": "string|null"
  }],
  "research": [{  // research output: papers, patents, software copyrights, thesis, lab/supervised research, research assistantship
    "type": "paper|patent|software_copyright|thesis|research_project|other",
    "title": "string",  // topic, paper, patent or software title
    "institution": "string|null",  // university, lab or institute
    "summary": "string",  // problem, methods, results; publication venue if any
    "start_date": "string|null", "end_date": "string|null"
  }],
  "skills": ["string"],  // one skill per item (split "Python/Java"); from the skills section and technologies named elsewhere; no duplicates
  "skill_groups": [{  // the skills section in full, one item per line/bullet, wording kept (proficiency, knowledge points); also fill skills from it
    "category": "string|null",  // the line's heading, e.g. "Backend Development"
    "description": "string"
  }],
  "educations": [{  // diploma or above, plus exchange programmes; skip secondary school
    "institution": "string",
    "entry_type": "degree|exchange",  // exchange = exchange/study abroad without a degree
    "degree": "bachelor|master|phd|diploma|not_applicable",  // exchange -> not_applicable
    "major": "string|null",
    "start_date": "string|null", "end_date": "string|null",
    "country": "string|null",
    "school_tier": "string|null",  // tier labels stated for the school, e.g. "985", "211, Double First-Class", "QS 52"
    "research_direction": "string|null",
    "gpa": "string|null",  // keep the scale, e.g. "3.92/4.00"
    "ranking": "string|null",  // e.g. "4/64", "Top 5%"
    "courses": ["string"]  // relevant coursework
  }],
  "certificates": [{"name": "string", "issuer": "string|null", "issue_date": "string|null", "expiry_date": "string|null",
    "score": "string|null"}],  // professional certifications and tests (e.g. CET-6 with score "527", IELTS)
  "languages": ["string"],  // human languages only, one per item; programming languages go in skills
  "awards": [{"name": "string", "date": "string|null"}],  // awards, scholarships, competition prizes, honorary titles
  "additional_info": ["string"]  // everything else, "Label: value"
}

Example
Resume text:
Wei Ming Tan
wei.ming.tan@example.com | +65 9123 4567

ABOUT
Final-year Computer Science student passionate about backend systems and cloud infrastructure.

EDUCATION
National University of Singapore
Bachelor of Computing, Computer Science
Aug 2022 - May 2026

EXPERIENCE
Backend Engineering Intern, Acme Technologies
May 2025 - Aug 2025
- Built REST APIs in Python/FastAPI serving 10k+ daily requests
- Migrated batch jobs from cron to Airflow, cutting failure rate by 30%

PROJECTS
Campus Marketplace (Personal Project)
- Full-stack marketplace app using React, Node.js and PostgreSQL
- Implemented JWT auth and Stripe checkout

SKILLS
Python, FastAPI, React, PostgreSQL, Docker, Git

CERTIFICATES
AWS Certified Cloud Practitioner, Amazon Web Services, 2024

LANGUAGES
English, Mandarin

Expected JSON:
{
  "name": "Wei Ming Tan", "email": "wei.ming.tan@example.com", "phone": "+65 9123 4567",
  "about": "Final-year Computer Science student passionate about backend systems and cloud infrastructure.",
  "experiences": [{
    "company": "Acme Technologies", "title": "Backend Engineering Intern",
    "employment_type": "internship", "start_date": "2025-05", "end_date": "2025-08",
    "description": "Built REST APIs in Python/FastAPI serving 10k+ daily requests\\nMigrated batch jobs from cron to Airflow, cutting failure rate by 30%",
    "country": null
  }],
  "projects": [{
    "title": "Campus Marketplace",
    "summary": "Full-stack marketplace app using React, Node.js and PostgreSQL\\nImplemented JWT auth and Stripe checkout",
    "technologies": ["React", "Node.js", "PostgreSQL"], "role": null,
    "start_date": null, "end_date": null
  }],
  "research": [],
  "skills": ["Python", "FastAPI", "React", "PostgreSQL", "Docker", "Git"],
  "skill_groups": [{"category": null, "description": "Python, FastAPI, React, PostgreSQL, Docker, Git"}],
  "educations": [{
    "institution": "National University of Singapore", "entry_type": "degree", "degree": "bachelor",
    "major": "Computer Science", "start_date": "2022-08", "end_date": "2026-05", "country": null,
    "school_tier": null, "research_direction": null, "gpa": null, "ranking": null, "courses": []
  }],
  "certificates": [{
    "name": "AWS Certified Cloud Practitioner", "issuer": "Amazon Web Services",
    "issue_date": "2024", "expiry_date": null, "score": null
  }],
  "languages": ["English", "Mandarin"],
  "awards": [],
  "additional_info": []
}
"""

CJK_PATTERN = re.compile(r"[\u3400-\u9fff]")


class ResumeParsingError(RuntimeError):
    """LLM 两次尝试后仍未能返回合法的 ParsedResume JSON。"""


class LLMResumeParser:
    def __init__(self, client: ChatClient | None = None) -> None:
        self.client = client or OpenAICompatibleClient()

    def parse(self, text: str) -> ParsedResume:
        raw = self.client.complete(system_prompt=SYSTEM_PROMPT, user_prompt=text)
        try:
            parsed = ParsedResume.model_validate_json(raw)
            self._ensure_english(parsed)
            return parsed
        except (json.JSONDecodeError, ValidationError, ValueError) as error:
            return self._retry(text, error)

    def _retry(self, text: str, error: Exception) -> ParsedResume:
        retry_prompt = (
            f"{text}\n\n"
            f"The previous output failed validation: {error}\n"
            "Return the complete JSON object again. Use English for every human-readable "
            "string value, translate or romanize all Chinese text, and output raw JSON only."
        )
        raw = self.client.complete(system_prompt=SYSTEM_PROMPT, user_prompt=retry_prompt)
        try:
            parsed = ParsedResume.model_validate_json(raw)
            self._ensure_english(parsed)
            return parsed
        except (json.JSONDecodeError, ValidationError, ValueError) as retry_error:
            raise ResumeParsingError(
                f"LLM 重试后仍未能返回合法的简历 JSON：{retry_error}"
            ) from retry_error

    @staticmethod
    def _ensure_english(parsed: ParsedResume) -> None:
        paths = _cjk_string_paths(parsed.model_dump())
        if paths:
            raise ValueError(
                "English-only output required; Chinese characters remained in: "
                + ", ".join(paths)
            )


def _cjk_string_paths(value: Any, path: str = "") -> list[str]:
    if isinstance(value, str):
        return [path] if CJK_PATTERN.search(value) else []
    if isinstance(value, dict):
        paths: list[str] = []
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            paths.extend(_cjk_string_paths(item, child_path))
        return paths
    if isinstance(value, list):
        paths = []
        for index, item in enumerate(value):
            paths.extend(_cjk_string_paths(item, f"{path}[{index}]"))
        return paths
    return []
