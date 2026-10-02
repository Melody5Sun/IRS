"""规则引擎和接口测试共用的造数据工具。

规则引擎读库只有 app/rule_engine/engine.py 的 _JOBS_SQL 一处，测试不建库，直接造它返回的岗位行：
make_rows 产出的键必须和 _JOBS_SQL 的列别名一一对应（id/status/company/employment_type/candidate_type/
remote_policy/degree_required/analysis_json/industry），SQL 加列时这里同步加键。SQL 本身用真实 PostgreSQL 验证。
"""

from app.rule_engine.constants import NOT_STATED
from app.schemas.profile import JobSearchConstraints, UserProfile
from app.schemas.resume import Education, Experience, ResumeDocument

_ANALYSIS_COLUMNS = ("employment_type", "candidate_type", "remote_policy", "degree_required")


def make_rows(*jobs: dict) -> list[dict]:
    """每个 dict 是一条岗位，id 默认按顺序从 1 开始。

    - status 默认 active，company / title 默认 c<id> / t<id>
    - industry 是公司所属行业（不给则和库里公司没有行业一样，为 not_stated）
    - required_skills / preferred_skills 写入 analysis_json（下游技能评分读这份文档）
    - analysis_json 可整体覆盖（用来造坏数据）
    - employment_type / candidate_type / remote_policy / degree_required 是 job_analyses 的列，不给为 not_stated
    """
    rows = []
    for index, job in enumerate(jobs, start=1):
        job_id = job.get("id", index)
        company = job.get("company", f"c{job_id}")
        title = job.get("title", f"t{job_id}")
        rows.append(
            {
                "id": job_id,
                "status": job.get("status", "active"),
                "company": company,
                **{column: job.get(column, NOT_STATED) for column in _ANALYSIS_COLUMNS},
                "analysis_json": job.get(
                    "analysis_json",
                    {
                        "job_id": job_id,
                        "company": company,
                        "title": title,
                        "required_skills": job.get("required_skills", []),
                        "preferred_skills": job.get("preferred_skills", []),
                    },
                ),
                "industry": job.get("industry", NOT_STATED),
            }
        )
    return rows


# 接口测试用的四个岗位：1、2 通过；3 行业不符；4 已下线
API_JOBS = (
    {"title": "Backend Engineer", "company": "Alpha", "industry": "Gaming",
     "employment_type": "internship", "required_skills": ["python", "sql"]},
    {"title": "Infra Engineer", "company": "Beta", "industry": "Gaming",
     "employment_type": "internship", "required_skills": ["kubernetes", "aws"]},
    {"title": "Web Engineer", "company": "Gamma", "industry": "Internet",
     "employment_type": "internship", "required_skills": ["python"]},
    {"title": "Old Job", "company": "Delta", "industry": "Gaming", "status": "inactive",
     "employment_type": "internship", "required_skills": ["python"]},
)


def make_api_profile(**overrides) -> UserProfile:
    """会通过 API_JOBS 里 1、2 号岗位的画像；overrides 覆盖求职约束。"""
    constraints = {"target_employment_types": ["internship"], "target_industries": ["Gaming"], **overrides}
    return make_profile(degrees=("bachelor",), skills=("Python", "SQL"), **constraints)


def make_profile(
    degrees: tuple[str, ...] = (),
    experience_types: tuple[str, ...] = (),
    exchange_only: bool = False,
    skills: tuple[str, ...] = (),
    **constraints,
) -> UserProfile:
    educations = [Education(institution="U", degree=degree) for degree in degrees]
    if exchange_only:
        educations = [Education(institution="U", entry_type="exchange", degree="not_applicable")]
    return UserProfile(
        resume=ResumeDocument(
            skills=list(skills),
            educations=educations,
            experiences=[Experience(company="C", title="T", employment_type=t) for t in experience_types],
        ),
        constraints=JobSearchConstraints(**constraints),
    )
