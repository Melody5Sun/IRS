import json

from app.services.openai_client_service import (
    ChatClient,
    OpenAICompatibleClient,
    llm_connection_settings,
)
from app.schemas.job import JobPosting, JobRequirementDocument


class GeminiService:
    def __init__(self, client: ChatClient | None = None) -> None:
        self._client_was_supplied = client is not None
        self.client = client or OpenAICompatibleClient()

    def is_configured(self) -> bool:
        return self._client_was_supplied or all(llm_connection_settings())

    def extract_job_requirements(self, job: JobPosting) -> JobRequirementDocument:
        raw_text = self.client.complete(
            system_prompt="You extract structured requirements from IT job descriptions.",
            user_prompt=self._build_prompt(job),
        )
        payload = self._parse_json_object(raw_text)
        payload = self._normalize_payload(payload, job)
        payload.setdefault("source_job_id", job.external_id)
        payload.setdefault("company", job.company)
        payload.setdefault("title", job.title)
        return JobRequirementDocument.model_validate(payload)

    def _build_prompt(self, job: JobPosting) -> str:
        return f"""
You are an information extraction system for IT CareerPilot.
Extract structured job requirements from the job description.

Rules:
- Output JSON only. Do not include markdown.
- Do not guess. If the JD does not explicitly state a value, use "not_stated", null, or [].
- Separate required skills from preferred skills based on explicit evidence.
- required_skills and preferred_skills must be arrays of skill names only, such as ["python", "java", "html"].
- Keep field names exactly aligned with the schema below.

Schema fields:
job_id, source_job_id, company, title, summary, employment_type, candidate_type,
location, remote_policy, degree_required, major_required, responsibilities,
required_skills, preferred_skills, keywords, source_evidence

Allowed values:
employment_type: internship, full_time, part_time, contract, freelance, not_stated
candidate_type: student, new_graduate, experienced, not_stated
remote_policy: onsite, hybrid, remote, not_stated
degree_required: bachelor, master, phd, diploma, not_applicable, not_stated

Job:
company: {job.company}
title: {job.title}
location: {job.location}
description:
{job.description}
""".strip()

    def _parse_json_object(self, text: str) -> dict:
        clean_text = text.strip()
        if clean_text.startswith("```"):
            clean_text = clean_text.strip("`")
            if clean_text.lower().startswith("json"):
                clean_text = clean_text[4:].strip()
        start = clean_text.find("{")
        end = clean_text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("Gemini response did not contain a JSON object.")
        return json.loads(clean_text[start : end + 1])

    def _normalize_payload(self, payload: dict, job: JobPosting) -> dict:
        normalized = dict(payload)

        from app.parsers.job_industry_classifier import classify_company_industry

        normalized["industry"] = classify_company_industry(job.company)

        if not isinstance(normalized.get("job_id"), int):
            normalized["job_id"] = job.id

        location = normalized.get("location")
        if isinstance(location, str):
            normalized["location"] = self._location_from_text(location)

        source_evidence = normalized.get("source_evidence")
        if isinstance(source_evidence, dict):
            normalized["source_evidence"] = [
                f"{key}: {value}"
                for key, value in source_evidence.items()
                if value
            ]
        elif isinstance(source_evidence, str):
            normalized["source_evidence"] = [source_evidence]

        for field_name in [
            "major_required",
            "responsibilities",
            "required_skills",
            "preferred_skills",
            "keywords",
            "source_evidence",
        ]:
            if normalized.get(field_name) is None:
                normalized[field_name] = []

        normalized["required_skills"] = self._normalize_skills(
            normalized.get("required_skills", []),
            "required",
        )
        normalized["preferred_skills"] = self._normalize_skills(
            normalized.get("preferred_skills", []),
            "preferred",
        )

        return normalized

    def _location_from_text(self, location: str) -> dict:
        if "singapore" in location.lower():
            return {"city": "Singapore", "country": "Singapore"}
        return {"city": location, "country": None}

    def _normalize_skills(self, skills: list | str, importance: str) -> list[str]:
        if isinstance(skills, str):
            skills = [skills]
        normalized_skills: dict[str, None] = {}
        for skill in skills:
            if isinstance(skill, str):
                skill_name = skill.strip().lower()
                if skill_name:
                    normalized_skills[skill_name] = None
                continue
            if isinstance(skill, dict) and skill.get("name"):
                skill_name = str(skill["name"]).strip().lower()
                if skill_name:
                    normalized_skills[skill_name] = None
        return list(normalized_skills.keys())
