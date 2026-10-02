import copy
import json

import pytest
from fastapi.testclient import TestClient

from app.api.routes import resumes as resumes_route
from app.main import app
from app.matching.scorer import calculate_experience_years
from app.resume.llm_resume_parser import SYSTEM_PROMPT, LLMResumeParser, ResumeParsingError
from app.resume.resume_parser import ResumeParser
from app.schemas.resume import Experience, ParsedResume
from app.services.profile_service import ProfileService
from app.services.resume_service import ResumeService

client = TestClient(app)

# 用户手动提交时的完整画像：选填字段（role、major、expiry_date）和可空列表（research）故意留空
COMPLETE_PROFILE = {
    "resume": {
        "name": "Jane Tan",
        "email": "jane@example.com",
        "phone": "+65 9123 4567",
        "experiences": [
            {
                "company": "Acme",
                "title": "Backend Intern",
                "employment_type": "internship",
                "start_date": "2024-01",
                "end_date": "2024-12",
                "description": "Built APIs with FastAPI.",
                "country": "Singapore",
            }
        ],
        "projects": [
            {"title": "Job Matcher", "summary": "Matching web app.", "technologies": ["Python"], "role": None}
        ],
        "research": [],
        "skills": ["Python", "SQL"],
        "educations": [
            {
                "institution": "NUS",
                "entry_type": "exchange",
                "degree": "not_applicable",
                "major": None,
                "start_date": "2024-09",
                "end_date": "2024-12",
                "country": "Singapore",
            }
        ],
        "certificates": [
            {"name": "AWS Cloud Practitioner", "issuer": "AWS", "issue_date": "2025-03", "expiry_date": None}
        ],
        "languages": ["English"],
    },
    "constraints": {
        "target_roles": ["Backend Developer"],
        "target_industries": ["Financial Technology (FinTech)"],
        "work_modes": ["hybrid", "remote"],
        "target_employment_types": ["full_time"],
        "notes": "Available from 2026-06.",
    },
}


class FakeChatClient:
    """按调用顺序依次返回预设的响应，模拟 LLM 输出，测试里不打真实 API。"""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        return self._responses.pop(0)


def _use_fake_llm(monkeypatch: pytest.MonkeyPatch, responses: list[str]) -> None:
    fake_parser = LLMResumeParser(client=FakeChatClient(responses))
    fake_service = ResumeService(parser=ResumeParser(llm_parser=fake_parser))
    monkeypatch.setattr(resumes_route, "resume_service", fake_service)


def _build_minimal_pdf(text: str) -> bytes:
    """手工拼一个最小的单页 PDF，避免为了测试引入新依赖。"""
    content = f"BT /F1 12 Tf 10 100 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >>"
        b" /MediaBox [0 0 200 200] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content),
    ]

    body = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body += b"%d 0 obj\n%s\nendobj\n" % (index, obj)

    xref_offset = len(body)
    body += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        body += b"%010d 00000 n \n" % offset
    body += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (
        len(objects) + 1,
        xref_offset,
    )
    return bytes(body)


def _upload_pdf(text: str = "Resume") -> dict:
    response = client.post(
        "/api/resumes/parse-pdf",
        files={"file": ("resume.pdf", _build_minimal_pdf(text), "application/pdf")},
    )
    assert response.status_code == 200
    return response.json()


def test_health_check() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_parse_resume_pdf_extracts_structured_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    llm_response = json.dumps(
        {
            "name": "Jane Tan",
            "email": "jane@example.com",
            "phone": "+65 9123 4567",
            "research": [
                {
                    "title": "Federated Learning for Edge Devices",
                    "institution": "NUS",
                    "summary": "Studied communication-efficient aggregation strategies.",
                    "start_date": "2025-01",
                    "end_date": "2025-05",
                }
            ],
            "experiences": [
                {
                    "company": "Acme",
                    "title": "Software Engineer Intern",
                    "employment_type": "internship",
                    "start_date": "2024-05",
                    "end_date": "2024-08",
                    "description": "Built APIs with FastAPI.",
                    "country": "Singapore",
                }
            ],
            "skills": ["Python"],
            "educations": [
                {
                    "institution": "NUS",
                    "entry_type": "degree",
                    "degree": "bachelor",
                    "major": "Computer Science",
                    "start_date": "2022-08",
                    "end_date": "2026-05",
                    "country": "Singapore",
                }
            ],
            "languages": ["English", "Mandarin"],
            "about": "Aspiring backend engineer.",
        }
    )
    _use_fake_llm(monkeypatch, [llm_response])

    body = _upload_pdf("Jane Tan")

    assert body["name"] == "Jane Tan"
    assert body["experiences"][0]["employment_type"] == "internship"
    assert body["skills"] == ["Python"]
    assert body["educations"][0]["entry_type"] == "degree"
    assert body["research"][0]["title"] == "Federated Learning for Edge Devices"
    assert body["languages"] == ["English", "Mandarin"]
    # about 只合并进画像的 notes，不出现在简历响应里
    assert "about" not in body


def test_system_prompt_covers_every_schema_field() -> None:
    # schema 改了字段但忘了同步 prompt 时，LLM 就不会输出该字段，这里提前拦住
    schema = ParsedResume.model_json_schema()
    models = [schema, *schema["$defs"].values()]
    fields = {key for model in models for key in model.get("properties", {})}

    missing = sorted(key for key in fields if f'"{key}"' not in SYSTEM_PROMPT)
    assert missing == []


def test_llm_parser_retries_once_on_invalid_json() -> None:
    valid_response = json.dumps({"name": "Retry Candidate"})
    parser = LLMResumeParser(client=FakeChatClient(["not valid json", valid_response]))

    assert parser.parse("some resume text").name == "Retry Candidate"


def test_llm_parser_raises_after_second_failure() -> None:
    parser = LLMResumeParser(client=FakeChatClient(["not valid json", "still not valid json"]))

    with pytest.raises(ResumeParsingError):
        parser.parse("some resume text")


def test_parse_resume_pdf_rejects_non_pdf_upload() -> None:
    response = client.post(
        "/api/resumes/parse-pdf",
        files={"file": ("resume.txt", b"not a pdf", "text/plain")},
    )

    assert response.status_code == 400


def test_profile_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_fake_llm(
        monkeypatch,
        [
            json.dumps({"name": "Jane Tan", "about": "Aspiring backend engineer."}),
            json.dumps({"name": "Jane Tan v2", "about": "Updated summary."}),
        ],
    )

    assert client.get("/api/profile").status_code == 404

    # 上传 PDF 后解析结果自动存入画像，简历里的 about 预填进 notes
    _upload_pdf("Jane Tan")
    saved = client.get("/api/profile").json()
    assert saved["resume"]["name"] == "Jane Tan"
    assert "about" not in saved["resume"]
    assert saved["constraints"] == {
        "target_roles": [],
        "target_industries": [],
        "work_modes": [],
        "target_employment_types": [],
        "notes": "Aspiring backend engineer.",
    }

    # 解析结果不完整，原样提交会被拒；补全后才能保存
    assert client.put("/api/profile", json=saved).status_code == 422
    response = client.put("/api/profile", json=COMPLETE_PROFILE)
    assert response.status_code == 200
    assert client.get("/api/profile").json() == COMPLETE_PROFILE

    # 重新上传简历：画像被替换；约束保留，用户写过的 notes 不被新 about 覆盖
    _upload_pdf("Jane Tan v2")
    reuploaded = client.get("/api/profile").json()
    assert reuploaded["resume"]["name"] == "Jane Tan v2"
    assert reuploaded["resume"]["skills"] == []
    assert reuploaded["constraints"] == COMPLETE_PROFILE["constraints"]


def test_resume_history_list_and_apply(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_fake_llm(
        monkeypatch,
        [
            json.dumps({"name": "Jane Tan v1"}),
            json.dumps({"name": "Jane Tan v2"}),
        ],
    )

    _upload_pdf("Jane Tan v1")
    _upload_pdf("Jane Tan v2")

    history = client.get("/api/resumes/history").json()
    # 按上传时间倒序，最新的在前面
    assert [entry["name"] for entry in history] == ["Jane Tan v2", "Jane Tan v1"]
    assert client.get("/api/profile").json()["resume"]["name"] == "Jane Tan v2"

    # 挑选更早的历史版本套用回当前画像
    older_id = history[1]["id"]
    applied = client.post(f"/api/resumes/history/{older_id}/apply")
    assert applied.status_code == 200
    assert applied.json()["resume"]["name"] == "Jane Tan v1"
    assert client.get("/api/profile").json()["resume"]["name"] == "Jane Tan v1"


def test_resume_history_apply_missing_id_returns_404() -> None:
    response = client.post("/api/resumes/history/999/apply")

    assert response.status_code == 404


def test_patch_profile_merges_partial_update() -> None:

    # 还没有画像时，PATCH 和 GET 一样返回 404
    assert client.patch("/api/profile", json={"constraints": {"notes": "hi"}}).status_code == 404

    client.put("/api/profile", json=COMPLETE_PROFILE)

    # 只传 constraints.notes，其余字段（包括 resume、constraints 里的其他字段）原样保留
    response = client.patch("/api/profile", json={"constraints": {"notes": "只改这一个字段"}})
    assert response.status_code == 200
    patched = response.json()
    assert patched["constraints"]["notes"] == "只改这一个字段"
    assert patched["constraints"]["target_roles"] == COMPLETE_PROFILE["constraints"]["target_roles"]
    assert patched["resume"] == COMPLETE_PROFILE["resume"]
    assert client.get("/api/profile").json() == patched

    # 非法枚举值仍然被拒绝（422），画像不受影响
    invalid_response = client.patch("/api/profile", json={"constraints": {"work_modes": ["office"]}})
    assert invalid_response.status_code == 422
    assert client.get("/api/profile").json() == patched


def test_profile_rejects_empty_fields(profile_service: ProfileService) -> None:
    profile = copy.deepcopy(COMPLETE_PROFILE)
    resume = profile["resume"]
    resume["email"] = None
    resume["experiences"][0]["employment_type"] = "not_stated"
    resume["experiences"][0]["country"] = " "
    resume["skills"] = []
    resume["languages"] = [""]
    profile["constraints"]["work_modes"] = []
    # notes 选填，留空不报错
    profile["constraints"]["notes"] = ""

    response = client.put("/api/profile", json=profile)

    assert response.status_code == 422
    assert [error["loc"] for error in response.json()["detail"]] == [
        ["body", "resume", "email"],
        ["body", "resume", "experiences", 0, "employment_type"],
        ["body", "resume", "experiences", 0, "country"],
        ["body", "resume", "skills"],
        ["body", "resume", "languages", 0],
        ["body", "constraints", "work_modes"],
    ]
    assert profile_service.get() is None


def test_profile_rejects_unknown_work_mode(profile_service: ProfileService) -> None:
    profile = copy.deepcopy(COMPLETE_PROFILE)
    profile["constraints"]["work_modes"] = ["office"]

    response = client.put("/api/profile", json=profile)

    assert response.status_code == 422
    assert profile_service.get() is None


def test_profile_rejects_unknown_employment_type(profile_service: ProfileService) -> None:
    profile = copy.deepcopy(COMPLETE_PROFILE)
    profile["constraints"]["target_employment_types"] = ["part_time"]

    response = client.put("/api/profile", json=profile)

    assert response.status_code == 422
    assert profile_service.get() is None


def test_profile_rejects_unknown_target_role_or_industry(profile_service: ProfileService) -> None:
    profile = copy.deepcopy(COMPLETE_PROFILE)
    profile["constraints"]["target_roles"] = ["Backend Engineer"]
    profile["constraints"]["target_industries"] = ["Fintech"]

    response = client.put("/api/profile", json=profile)

    assert response.status_code == 422
    assert profile_service.get() is None


def test_profile_options_expose_role_categories_and_industries() -> None:
    response = client.get("/api/profile/options")

    assert response.status_code == 200
    body = response.json()
    assert "Software Development" in body["target_role_categories"]
    assert "Backend Developer" in body["target_role_categories"]["Software Development"]
    assert "Financial Technology (FinTech)" in body["target_industries"]
    # 生成式 AI 浪潮下新出现的岗位也应该在预设列表里
    assert "AI Engineer" in body["target_role_categories"]["AI & Machine Learning"]
    assert "AI Product Manager" in body["target_role_categories"]["Product & Project Management"]


def test_analyze_job_requirements_extracts_structured_document() -> None:
    response = client.post(
        "/api/jobs/analyze-requirements",
        json={
            "job_id": "job-1",
            "title": "Software Engineer Intern",
            "company": "Acme",
            "description": "Required experience with Python and SQL. Docker is a plus.",
            "location": "Singapore",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["employment_type"] == "internship"
    assert body["candidate_type"] == "student"
    assert set(body["required_skills"]) == {"python", "sql"}
    assert body["preferred_skills"] == ["docker"]


def test_recommendations_rank_matching_job_first() -> None:
    response = client.post(
        "/api/recommendations",
        json={
            "candidate": {
                "name": "Jane Tan",
                "skills": ["Python", "React", "SQL"],
                "experiences": [
                    {
                        "company": "Acme",
                        "title": "Developer",
                        "start_date": "2023-01",
                        "end_date": "2024-12",
                    }
                ],
            },
            "jobs": [
                {
                    "job_id": "job-1",
                    "title": "Software Engineer Intern",
                    "company": "Acme",
                    "description": "Build APIs with Python, FastAPI and SQL.",
                },
                {
                    "job_id": "job-2",
                    "title": "Frontend Intern",
                    "company": "Beta",
                    "description": "Build UI with TypeScript and CSS.",
                },
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommendations"][0]["job_id"] == "job-1"
    assert body["recommendations"][0]["eligible"] is True


def test_parsed_resume_feeds_recommendations(monkeypatch: pytest.MonkeyPatch) -> None:
    llm_response = json.dumps(
        {
            "name": "Jane Tan",
            "skills": ["Python", "FastAPI", "Docker"],
            "experiences": [
                {
                    "company": "Acme",
                    "title": "Backend Intern",
                    "employment_type": "internship",
                    "start_date": "2024-01",
                    "end_date": "2024-12",
                }
            ],
        }
    )
    _use_fake_llm(monkeypatch, [llm_response])
    parsed = _upload_pdf("Jane Tan")

    job = {
        "title": "Backend Intern",
        "company": "Acme",
        "description": "Build APIs with Python, FastAPI and SQL.",
    }
    response = client.post(
        "/api/recommendations",
        json={
            "candidate": parsed,
            "jobs": [
                {**job, "job_id": "backend"},
            ],
        },
    )

    assert response.status_code == 200
    items = {item["job_id"]: item for item in response.json()["recommendations"]}
    assert items["backend"]["eligible"] is True
    assert items["backend"]["matched_skills"] == ["fastapi", "python"]
    assert items["backend"]["missing_skills"] == ["sql"]


def test_experience_years_merges_overlaps_and_handles_partial_dates() -> None:
    def exp(start: str | None, end: str | None) -> Experience:
        return Experience(company="c", title="t", start_date=start, end_date=end)

    # 1-6 月和 4-12 月重叠，合计 12 个月；缺开始日期的跳过；缺结束日期的只算 1 个月
    overlapping = [exp("2023-01", "2023-06"), exp("2023-04", "2023-12"), exp(None, "2024"), exp("2025-03", None)]
    assert calculate_experience_years(overlapping) == 1.1
    assert calculate_experience_years([exp("2021", "2021")]) == 1.0
    assert calculate_experience_years([exp("2024-01", "present")]) > 0
    assert calculate_experience_years([]) == 0
