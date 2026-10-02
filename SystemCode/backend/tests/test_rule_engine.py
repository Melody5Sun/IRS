import logging

import pytest
from job_db import make_profile, make_rows

from app.rule_engine import screen_rows
from app.rule_engine.engine import count_rejections
from app.schemas.profile import UserProfile


def kept_ids(profile: UserProfile, *jobs: dict) -> list[int]:
    return [document.job_id for document in screen_rows(profile, make_rows(*jobs)).documents]


# ---------- 规则 1：状态 ----------

def test_status_keeps_active_and_rejects_inactive() -> None:
    assert kept_ids(make_profile(), {"status": "active"}, {"status": "inactive"}) == [1]


# ---------- 规则 2：学历 ----------

@pytest.mark.parametrize(
    ("degrees", "required", "kept"),
    [
        (("bachelor",), "master", False),  # 低于要求：剔除
        (("master",), "master", True),  # 恰好等于要求：保留
        (("bachelor", "phd", "diploma"), "phd", True),  # 最高学历在列表中间
        (("diploma",), "bachelor", False),
        ((), "phd", True),  # 无学历条目：学生侧缺失，不约束
        (("bachelor",), "not_stated", True),
        (("diploma",), "not_applicable", True),
    ],
)
def test_degree(degrees: tuple[str, ...], required: str, kept: bool) -> None:
    assert (kept_ids(make_profile(degrees), {"degree_required": required}) == [1]) is kept


def test_degree_exchange_only_is_treated_as_missing() -> None:
    assert kept_ids(make_profile(exchange_only=True), {"degree_required": "phd"}) == [1]


# ---------- 规则 3：工作模式 ----------

@pytest.mark.parametrize(
    ("work_modes", "policy", "kept"),
    [
        (["onsite"], "hybrid", True),  # hybrid 岗位配任意 work_modes 都放行
        (["remote"], "hybrid", True),
        (["remote"], "onsite", False),  # onsite 岗位配只选 remote 的学生：剔除
        (["onsite", "remote"], "remote", True),
        ([], "onsite", True),  # 学生 work_modes 为空：不约束
        (["hybrid"], "onsite", False),  # 学生只选 hybrid 遇到 onsite 岗位：按字面剔除
        (["hybrid"], "remote", False),
        (["remote"], "not_stated", True),
    ],
)
def test_work_mode(work_modes: list[str], policy: str, kept: bool) -> None:
    profile = make_profile(work_modes=work_modes)
    assert (kept_ids(profile, {"remote_policy": policy}) == [1]) is kept


# ---------- 规则 4：雇佣类型 ----------

@pytest.mark.parametrize(
    ("types", "employment_type", "kept"),
    [
        (["internship"], "internship", True),
        (["internship"], "full_time", False),
        (["internship", "full_time"], "full_time", True),
        (["internship"], "contract", False),
        ([], "full_time", True),  # 学生 target_employment_types 为空：不约束
        (["full_time"], "not_stated", True),  # 岗位 not_stated：不约束
    ],
)
def test_employment_type(types: list[str], employment_type: str, kept: bool) -> None:
    profile = make_profile(target_employment_types=types)
    assert (kept_ids(profile, {"employment_type": employment_type}) == [1]) is kept


# ---------- 规则 5：候选人类型 ----------

@pytest.mark.parametrize(
    ("experience_types", "candidate_type", "kept"),
    [
        ((), "experienced", False),  # experiences 为空：剔除（本规则不放行学生侧缺失）
        ((None,), "experienced", False),  # 解析时没判断出类型（用户还没填）：不算全职经历
        (("internship",), "experienced", False),  # 只有实习经历
        (("internship", "full_time"), "experienced", True),
        ((), "student", True),
        ((), "new_graduate", True),
        ((), "not_stated", True),
    ],
)
def test_candidate_type(experience_types: tuple[str | None, ...], candidate_type: str, kept: bool) -> None:
    profile = make_profile(experience_types=experience_types)
    assert (kept_ids(profile, {"candidate_type": candidate_type}) == [1]) is kept


# ---------- 规则 6：行业 ----------

def test_industry_keeps_matching_and_rejects_others() -> None:
    profile = make_profile(target_industries=["Gaming"])
    assert kept_ids(profile, {"industry": "Gaming"}, {"industry": "Internet"}) == [1]


def test_industry_empty_student_list_is_unconstrained() -> None:
    assert kept_ids(make_profile(), {"industry": "Gaming"}, {"industry": "Internet"}) == [1, 2]


def test_company_without_industry_record_is_unconstrained() -> None:
    assert kept_ids(make_profile(target_industries=["Gaming"]), {"company": "Unknown Co"}) == [1]


# ---------- 通用原则 ----------

def test_unknown_job_value_is_unconstrained_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    profile = make_profile(
        degrees=("diploma",),
        work_modes=["onsite"],
        target_employment_types=["internship"],
        target_industries=["Gaming"],
    )
    job = {
        "degree_required": "doctorate",
        "remote_policy": "flexible",
        "employment_type": "temp",
        "candidate_type": "senior_pro",
        "industry": "Farming",
    }
    with caplog.at_level(logging.WARNING, logger="app.rule_engine.engine"):
        assert kept_ids(profile, job) == [1]
    assert len(caplog.records) == 5


def test_blank_job_value_is_unconstrained() -> None:
    profile = make_profile(target_industries=["Gaming"], work_modes=["onsite"])
    assert kept_ids(profile, {"industry": " ", "remote_policy": ""}) == [1]


def test_rejections_record_every_failed_rule() -> None:
    profile = make_profile(("bachelor",), target_industries=["Gaming"])
    result = screen_rows(profile, make_rows({"status": "inactive", "degree_required": "phd", "industry": "Internet"}))
    assert result.documents == []
    assert result.rejected_by_rule == {"degree": 1, "industry": 1, "status": 1}


# ---------- screen_rows：输出通过筛选的岗位文档 ----------

def test_screen_rows_returns_documents_of_kept_jobs_with_stats() -> None:
    rows = make_rows(
        {"title": "Keep", "company": "Alpha", "industry": "Gaming", "required_skills": ["python"]},
        {"industry": "Internet"},
        {"status": "inactive", "industry": "Gaming"},
    )
    result = screen_rows(make_profile(target_industries=["Gaming"]), rows)
    assert [document.job_id for document in result.documents] == [1]
    document = result.documents[0]
    assert (document.title, document.company, document.industry, document.required_skills) == (
        "Keep",
        "Alpha",
        "Gaming",
        ["python"],
    )
    assert result.total_jobs == 3
    assert result.rejected_by_rule == {"industry": 1, "status": 1}


def test_screen_rows_fills_industry_from_company_not_from_analysis_json() -> None:
    # 文档上的行业以公司表为准；公司没有行业时保持文档默认值
    documents = screen_rows(make_profile(), make_rows({"industry": "Cybersecurity"}, {})).documents
    assert [document.industry for document in documents] == ["Cybersecurity", "Software & IT Services"]


def test_screen_rows_skips_unparseable_analysis_json_with_warning(caplog: pytest.LogCaptureFixture) -> None:
    # 缺 title 等必填字段的 raw_analysis 还原不成 JobRequirementDocument
    rows = make_rows({"analysis_json": {"required_skills": ["python"]}}, {})
    with caplog.at_level(logging.WARNING, logger="app.rule_engine.engine"):
        result = screen_rows(make_profile(), rows)
    assert [document.job_id for document in result.documents] == [2]
    assert result.total_jobs == 2
    assert "无法解析" in caplog.text


def test_count_rejections_counts_each_rule_separately() -> None:
    assert count_rejections({1: {"status", "degree"}, 2: {"degree"}}) == {"degree": 2, "status": 1}


# ---------- 端到端 persona ----------

PERSONA_JOBS = (
    # 1 本科实习，现场，AI
    {"employment_type": "internship", "candidate_type": "student", "degree_required": "bachelor",
     "remote_policy": "onsite", "industry": "Artificial Intelligence"},
    # 2 硕士要求实习，混合，FinTech
    {"employment_type": "internship", "candidate_type": "student", "degree_required": "master",
     "remote_policy": "hybrid", "industry": "Financial Technology (FinTech)"},
    # 3 校招全职，远程，软件
    {"employment_type": "full_time", "candidate_type": "new_graduate", "degree_required": "master",
     "remote_policy": "remote", "industry": "Software & IT Services"},
    # 4 有经验全职，未说明工作模式，软件
    {"employment_type": "full_time", "candidate_type": "experienced", "degree_required": "bachelor",
     "industry": "Software & IT Services"},
    # 5 已下线的实习
    {"status": "inactive", "employment_type": "internship", "industry": "Artificial Intelligence"},
)


def test_persona_bachelor_seeking_internship() -> None:
    profile = make_profile(
        ("bachelor",),
        ("internship",),
        work_modes=["onsite", "hybrid"],
        target_employment_types=["internship"],
        target_industries=["Artificial Intelligence", "Financial Technology (FinTech)"],
    )
    # 2 学历不够；3、4 是全职；5 已下线
    assert kept_ids(profile, *PERSONA_JOBS) == [1]


def test_persona_master_seeking_graduate_job() -> None:
    profile = make_profile(
        ("bachelor", "master"),
        ("internship",),
        work_modes=["remote", "hybrid"],
        target_employment_types=["full_time", "internship"],
        target_industries=["Software & IT Services", "Financial Technology (FinTech)"],
    )
    # 1 行业和工作模式都不符；4 需要全职经验；5 已下线
    assert kept_ids(profile, *PERSONA_JOBS) == [2, 3]


def test_persona_experienced_seeking_experienced_job() -> None:
    profile = make_profile(
        ("bachelor",),
        ("internship", "full_time"),
        target_employment_types=["full_time"],
        target_industries=["Software & IT Services"],
    )
    # 3 要求硕士；1、2 是实习；5 已下线
    assert kept_ids(profile, *PERSONA_JOBS) == [4]
