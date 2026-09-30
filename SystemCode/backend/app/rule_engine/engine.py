"""主流程：读库 -> 清洗岗位字段 -> 构造学生 fact -> 运行规则 -> 输出通过全部规则的岗位 id / 岗位文档。"""

import json
import logging
import sqlite3
from collections.abc import Mapping
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text

from app.db.postgres import get_postgres_engine
from app.parsers.job_industry_classifier import normalize_company_name
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

# 取 job_analysis 全部列：新规则用到新列时不需要改这里的 SQL
# 行业不在 job_analysis 里（按公司存在 company_industries），所以额外带上 j.company 用来查行业
_JOBS_SQL = """
    SELECT j.id AS id, j.status AS status, j.company AS company, a.*
    FROM jobs j
    JOIN job_analysis a ON a.job_id = j.id
    ORDER BY j.id
"""


@dataclass(frozen=True)
class ScreeningResult:
    """规则引擎的筛选结果：通过的岗位文档 + 统计（供接口和 CLI 共用）。"""

    documents: list[JobRequirementDocument]
    total_jobs: int  # 有分析记录的岗位总数（通过 + 被剔除）
    rejected_by_rule: dict[str, int]  # 各规则单独剔除数，一个岗位可被多条规则同时剔除，所以不是累计


def load_company_industries(connection: sqlite3.Connection) -> dict[str, str]:
    """读取 规范化公司名 -> 行业 的映射；旧库没有这张表时告警并返回空映射，而不是静默漏掉行业规则。"""
    try:
        return {row[0]: row[1] for row in connection.execute("SELECT normalized_company, industry FROM company_industries")}
    except sqlite3.OperationalError:
        logger.warning("库中没有 company_industries 表，行业规则不会生效（岗位行业按 not_stated 处理）")
        return {}


def load_job_facts(connection: sqlite3.Connection) -> list[Job]:
    """读取有分析记录的岗位；词表内的字段做清洗：空值 -> not_stated，未知值 -> not_stated 并记日志。"""
    connection.row_factory = sqlite3.Row
    industries = load_company_industries(connection)
    facts = []
    for row in connection.execute(_JOBS_SQL):
        fields = {key: row[key] for key in row.keys() if key != "job_id"}
        # 行业按公司取：公司不在映射里时不约束
        fields["industry"] = industries.get(normalize_company_name(fields["company"]), NOT_STATED)
        for field, vocab in JOB_FIELD_VOCAB.items():
            value = fields.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                fields[field] = NOT_STATED
            elif value not in vocab:
                logger.warning("岗位 %s 的 %s 取值 %r 不在词表内，按不约束处理", fields["id"], field, value)
                fields[field] = NOT_STATED
        facts.append(Job(**fields))
    return facts


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


def _run_rules(profile: UserProfile, connection: sqlite3.Connection) -> tuple[list[Job], dict[int, set[str]]]:
    job_facts = load_job_facts(connection)
    engine = FilterEngine()
    engine.reset()
    engine.declare(build_student_fact(profile))
    for fact in job_facts:
        engine.declare(fact)
    engine.run()
    return job_facts, engine.rejections


def evaluate(profile: UserProfile, connection: sqlite3.Connection) -> tuple[list[int], dict[int, set[str]]]:
    """返回 (通过全部规则的岗位 id 升序列表, 岗位 id -> 剔除它的规则名集合)。"""
    job_facts, rejections = _run_rules(profile, connection)
    kept = [fact["id"] for fact in job_facts if fact["id"] not in rejections]
    return kept, rejections


def count_rejections(rejections: dict[int, set[str]]) -> dict[str, int]:
    """各规则单独剔除的岗位数（不管其他规则是否也剔除了它，所以各项相加会大于实际剔除总数）。"""
    per_rule = Counter(rule for rules in rejections.values() for rule in rules)
    return dict(sorted(per_rule.items()))


def connect_read_only(db_path: str | Path) -> sqlite3.Connection:
    # mode=ro：文件不存在时直接报错，不会像默认模式那样新建一个空库
    return sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)


def filter_jobs(profile: UserProfile, db_path: str | Path) -> dict:
    connection = connect_read_only(db_path)
    try:
        kept, _ = evaluate(profile, connection)
    finally:
        connection.close()
    return {"job_ids": kept}


def _to_document(fact: Job) -> JobRequirementDocument | None:
    """把岗位 fact 里的 analysis_json 还原成 JobRequirementDocument；解析失败返回 None。"""
    try:
        raw_payload = fact["analysis_json"]
        payload = dict(raw_payload) if isinstance(raw_payload, Mapping) else json.loads(raw_payload)
        payload = dict(payload)
        payload["job_id"] = fact["id"]  # 以库里的主键为准
        # 行业不再存进 analysis_json，读回来只会是默认值，所以这里用按公司查到的行业覆盖
        payload.pop("industry", None)
        if fact["industry"] != NOT_STATED:
            payload["industry"] = fact["industry"]
        return JobRequirementDocument.model_validate(payload)
    except (ValueError, TypeError):
        logger.warning("岗位 %s 的 analysis_json 无法解析成 JobRequirementDocument，已跳过", fact["id"])
        return None


def screen_jobs(profile: UserProfile, db_path: str | Path) -> ScreeningResult:
    """硬约束初筛：返回通过全部规则的岗位文档（按 job_id 升序）和统计，供下游技能评分使用。"""
    connection = connect_read_only(db_path)
    try:
        job_facts, rejections = _run_rules(profile, connection)
    finally:
        connection.close()
    documents = [
        document
        for fact in job_facts
        if fact["id"] not in rejections and (document := _to_document(fact)) is not None
    ]
    return ScreeningResult(
        documents=documents,
        total_jobs=len(job_facts),
        rejected_by_rule=count_rejections(rejections),
    )


def screen_jobs_postgres(profile: UserProfile) -> ScreeningResult:
    """Run the existing rule engine against the normalized PostgreSQL schema."""
    query = text(
        """
        SELECT jp.id, jp.status, c.name AS company, ja.summary,
               ja.employment_type, ja.candidate_type, ja.remote_policy,
               ja.degree_required, ja.raw_analysis AS analysis_json,
               COALESCE(industry.name, :not_stated) AS industry
        FROM job_postings jp
        JOIN companies c ON c.id = jp.company_id
        JOIN job_analyses ja ON ja.job_id = jp.id
        LEFT JOIN industries industry ON industry.id = c.industry_id
        ORDER BY jp.id
        """
    )
    with get_postgres_engine().connect() as connection:
        rows = connection.execute(query, {"not_stated": NOT_STATED}).mappings().all()
    facts: list[Job] = []
    for row in rows:
        fields = dict(row)
        for field, vocab in JOB_FIELD_VOCAB.items():
            value = fields.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                fields[field] = NOT_STATED
            elif value not in vocab:
                logger.warning(
                    "岗位 %s 的 %s 取值 %r 不在词表内，按不约束处理",
                    fields["id"],
                    field,
                    value,
                )
                fields[field] = NOT_STATED
        facts.append(Job(**fields))

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
