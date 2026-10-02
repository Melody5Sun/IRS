"""主流程：读 PostgreSQL 岗位 -> 清洗岗位字段 -> 构造学生 fact -> 运行规则 -> 输出通过全部规则的岗位文档。"""

import json
import logging
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import text

from app.db.postgres import get_postgres_engine
from app.rule_engine.constants import (
    DEGREE_RANK,
    FULL_TIME_EMPLOYMENT,
    JOB_FIELD_VOCAB,
    NOT_STATED,
    STUDENT_DEGREE_MISSING_RANK,
)
from app.rule_engine.rules import FilterEngine, Job, Student
from app.schemas.job import JobRequirementDocument
from app.schemas.profile import UserProfile

logger = logging.getLogger(__name__)

# 只取有分析记录的岗位（INNER JOIN job_analyses）；行业按公司存在 companies.industry_id，公司没有行业时为 not_stated。
# 新规则用到 job_analyses 的新列时，在这里加列并在 tests/job_db.py 的 make_rows 里同步加同名键
_JOBS_SQL = text(
    """
    SELECT jp.id, jp.status, c.name AS company,
           ja.employment_type, ja.candidate_type, ja.remote_policy, ja.degree_required,
           ja.raw_analysis AS analysis_json,
           COALESCE(industry.name, :not_stated) AS industry
    FROM job_postings jp
    JOIN companies c ON c.id = jp.company_id
    JOIN job_analyses ja ON ja.job_id = jp.id
    LEFT JOIN industries industry ON industry.id = c.industry_id
    ORDER BY jp.id
    """
)


@dataclass(frozen=True)
class ScreeningResult:
    """规则引擎的筛选结果：通过的岗位文档 + 统计（供接口和 CLI 共用）。"""

    documents: list[JobRequirementDocument]
    total_jobs: int  # 有分析记录的岗位总数（通过 + 被剔除）
    rejected_by_rule: dict[str, int]  # 各规则单独剔除数，一个岗位可被多条规则同时剔除，所以不是累计


def load_job_rows() -> list[dict]:
    with get_postgres_engine().connect() as connection:
        rows = connection.execute(_JOBS_SQL, {"not_stated": NOT_STATED}).mappings().all()
    return [dict(row) for row in rows]


def to_job_fact(row: Mapping) -> Job:
    """词表内的字段做清洗：空值 -> not_stated，未知值 -> not_stated 并记日志。"""
    fields = dict(row)
    for field, vocab in JOB_FIELD_VOCAB.items():
        value = fields.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            fields[field] = NOT_STATED
        elif value not in vocab:
            logger.warning("岗位 %s 的 %s 取值 %r 不在词表内，按不约束处理", fields["id"], field, value)
            fields[field] = NOT_STATED
    return Job(**fields)


def build_student_fact(profile: UserProfile) -> Student:
    resume, constraints = profile.resume, profile.constraints
    # 学历取所有条目中等级最高的一个（含在读），无条目时等同于学生侧缺失
    degree_rank = max(
        (DEGREE_RANK[education.degree] for education in resume.educations),
        default=STUDENT_DEGREE_MISSING_RANK,
    )
    return Student(
        degree_rank=degree_rank,
        work_modes=list(constraints.work_modes),
        employment_types=list(constraints.target_employment_types),
        industries=list(constraints.target_industries),
        has_full_time_experience=any(
            experience.employment_type == FULL_TIME_EMPLOYMENT for experience in resume.experiences
        ),
    )


def count_rejections(rejections: dict[int, set[str]]) -> dict[str, int]:
    """各规则单独剔除的岗位数（不管其他规则是否也剔除了它，所以各项相加会大于实际剔除总数）。"""
    per_rule = Counter(rule for rules in rejections.values() for rule in rules)
    return dict(sorted(per_rule.items()))


def _to_document(fact: Job) -> JobRequirementDocument | None:
    """把岗位 fact 里的 analysis_json 还原成 JobRequirementDocument；解析失败返回 None。"""
    try:
        raw_payload = fact["analysis_json"]
        payload = dict(raw_payload) if isinstance(raw_payload, Mapping) else json.loads(raw_payload)
        payload["job_id"] = fact["id"]  # 以库里的主键为准
        # 行业以公司表为准，analysis_json 里的旧值不用
        payload.pop("industry", None)
        if fact["industry"] != NOT_STATED:
            payload["industry"] = fact["industry"]
        return JobRequirementDocument.model_validate(payload)
    except (ValueError, TypeError):
        logger.warning("岗位 %s 的 analysis_json 无法解析成 JobRequirementDocument，已跳过", fact["id"])
        return None


def screen_rows(profile: UserProfile, rows: list[Mapping]) -> ScreeningResult:
    """纯函数：对给定的岗位行跑全部规则，返回通过的岗位文档（按输入顺序）和统计。"""
    facts = [to_job_fact(row) for row in rows]
    engine = FilterEngine()
    engine.reset()
    engine.declare(build_student_fact(profile))
    for fact in facts:
        engine.declare(fact)
    engine.run()
    rejections = engine.rejections
    documents = [
        document
        for fact in facts
        if fact["id"] not in rejections and (document := _to_document(fact)) is not None
    ]
    return ScreeningResult(
        documents=documents,
        total_jobs=len(facts),
        rejected_by_rule=count_rejections(rejections),
    )


def screen_jobs(profile: UserProfile) -> ScreeningResult:
    """硬约束初筛：读库里全部岗位跑规则，供 /rules-screening、/ranking 和 CLI 使用。"""
    return screen_rows(profile, load_job_rows())
