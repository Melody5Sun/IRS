from datetime import datetime, timezone

from app.matching.overall_scorer import OverallScorer
from app.repositories.job_repository import JobRepository
from app.repositories.job_semantic_repository import JobSemanticRepository
from app.schemas.job_match_detail import (
    JobMatchComponentPoints,
    JobMatchDetailJob,
    JobMatchDetailMeta,
    JobMatchDetailResponse,
    JobMatchDetailScore,
    JobMatchEvidence,
    JobMatchGap,
    JobMatchRecommendation,
)
from app.schemas.match import (
    CareerIntentScoreRequest,
    CareerIntentScoreResponse,
    ResponsibilityScoreRequest,
    ResponsibilityScoreResponse,
    SkillScoreRequest,
    SkillScoreResponse,
)
from app.schemas.profile import UserProfile
from app.services.career_intent_match_service import CareerIntentMatchService
from app.services.responsibility_match_service import ResponsibilityMatchService
from app.services.skill_match_service import SkillMatchService


class JobMatchDetailNotFoundError(LookupError):
    pass


class JobMatchDetailAnalysisUnavailableError(RuntimeError):
    pass


class JobMatchDetailService:
    ALGORITHM_VERSION = "job-match-detail-v1"

    def __init__(
        self,
        job_repository: JobRepository | None = None,
        semantic_repository: JobSemanticRepository | None = None,
        skill_match_service: SkillMatchService | None = None,
        responsibility_match_service: ResponsibilityMatchService | None = None,
        career_intent_match_service: CareerIntentMatchService | None = None,
        overall_scorer: OverallScorer | None = None,
    ) -> None:
        self.job_repository = job_repository or JobRepository()
        self.semantic_repository = semantic_repository or JobSemanticRepository()
        self.skill_match_service = skill_match_service or SkillMatchService()
        self.responsibility_match_service = (
            responsibility_match_service or ResponsibilityMatchService()
        )
        self.career_intent_match_service = (
            career_intent_match_service or CareerIntentMatchService()
        )
        self.overall_scorer = overall_scorer or OverallScorer()

    def get_detail(self, job_id: int, profile: UserProfile) -> JobMatchDetailResponse:
        posting = self.job_repository.get_job(job_id)
        if posting is None:
            raise JobMatchDetailNotFoundError(f"Job {job_id} was not found.")
        job = self.semantic_repository.get_analyzed_job(job_id)
        if job is None:
            raise JobMatchDetailAnalysisUnavailableError(
                f"Job {job_id} has no structured analysis."
            )

        skill_score = self.skill_match_service.score(
            SkillScoreRequest(candidate=profile.resume, job=job)
        )
        responsibility_score = self.responsibility_match_service.score(
            ResponsibilityScoreRequest(candidate=profile.resume, job=job)
        )
        career_intent_score = self.career_intent_match_service.score(
            CareerIntentScoreRequest(
                target_roles=profile.constraints.target_roles,
                job=job,
            )
        )
        overall_score = self.overall_scorer.combine(
            skill_score,
            responsibility_score,
            career_intent_score,
        )

        return JobMatchDetailResponse(
            job=JobMatchDetailJob(
                job_id=job_id,
                source=posting.source,
                company=posting.company,
                title=posting.title,
                location=posting.location,
                employment_type=job.employment_type,
                url=posting.url,
                description=posting.description,
                summary=job.summary,
                responsibilities=job.responsibilities,
                required_skills=job.required_skills,
                preferred_skills=job.preferred_skills,
                collected_at=posting.collected_at,
            ),
            match=JobMatchDetailScore(
                calculable=overall_score.calculable,
                final_score=overall_score.final_score,
                core_score=overall_score.core_score,
                preferred_skill_bonus=overall_score.preferred_bonus,
                active_core_weight=overall_score.active_core_weight,
                component_points=JobMatchComponentPoints(
                    required_skill_direct=skill_score.required_direct_points,
                    responsibility=responsibility_score.responsibility_points,
                    required_skill_graph=skill_score.required_graph_points,
                    career_intent=career_intent_score.career_intent_points,
                ),
                effective_weights=overall_score.effective_weights,
                normalized_contributions=overall_score.normalized_contributions,
            ),
            recommendation=self._recommendation(
                posting.title,
                overall_score.final_score,
                skill_score,
                responsibility_score,
                career_intent_score,
            ),
            gaps=self._gaps(
                skill_score,
                responsibility_score,
                career_intent_score,
            ),
            meta=JobMatchDetailMeta(
                algorithm_version=self.ALGORITHM_VERSION,
                generated_at=datetime.now(timezone.utc),
            ),
        )

    def _recommendation(
        self,
        job_title: str,
        final_score: float,
        skill: SkillScoreResponse,
        responsibility: ResponsibilityScoreResponse,
        career_intent: CareerIntentScoreResponse,
    ) -> JobMatchRecommendation:
        highlights: list[str] = []
        evidence: list[JobMatchEvidence] = []

        required_total = (
            len(skill.direct_required_matches)
            + len(skill.graph_required_matches)
            + len(skill.missing_required_skills)
        )
        if skill.required_skills_calculable:
            direct_count = len(skill.direct_required_matches)
            highlights.append(f"直接满足 {direct_count}/{required_total} 项必须技能")
        if skill.graph_required_matches:
            highlights.append(
                f"另有 {len(skill.graph_required_matches)} 项必须技能可通过相关技能迁移"
            )
        if responsibility.responsibilities_calculable:
            matched_count = sum(
                item.status != "missing" for item in responsibility.matches
            )
            highlights.append(
                f"{matched_count}/{responsibility.responsibility_count} 项岗位职责能够找到简历证据"
            )
        if career_intent.intent_calculable and career_intent.best_target_role:
            highlights.append(
                f"求职意向 {career_intent.best_target_role} 与该岗位的方向匹配度为 "
                f"{career_intent.intent_coverage:.0f}%"
            )
        preferred_count = (
            len(skill.direct_preferred_matches) + len(skill.graph_preferred_matches)
        )
        if skill.preferred_skills_available:
            highlights.append(
                f"匹配 {preferred_count} 项加分技能，获得 {skill.preferred_bonus:.1f} 分加分"
            )

        for item in skill.direct_required_matches:
            evidence.append(
                JobMatchEvidence(
                    requirement=item.jd_skill,
                    candidate_evidence=item.candidate_skill,
                    evidence_source="skills",
                    match_type="direct_skill",
                    similarity=1.0,
                )
            )
        for item in skill.graph_required_matches:
            evidence.append(
                JobMatchEvidence(
                    requirement=item.jd_skill,
                    candidate_evidence=item.candidate_skill,
                    evidence_source="skills",
                    match_type="knowledge_graph",
                    similarity=item.relation_score,
                    relation=item.relation,
                    path=item.path,
                )
            )
        for item in skill.direct_preferred_matches:
            evidence.append(
                JobMatchEvidence(
                    requirement=item.jd_skill,
                    candidate_evidence=item.candidate_skill,
                    evidence_source="skills",
                    match_type="preferred_skill",
                    similarity=1.0,
                )
            )
        for item in skill.graph_preferred_matches:
            evidence.append(
                JobMatchEvidence(
                    requirement=item.jd_skill,
                    candidate_evidence=item.candidate_skill,
                    evidence_source="skills",
                    match_type="preferred_skill",
                    similarity=item.relation_score,
                    relation=item.relation,
                    path=item.path,
                )
            )
        for item in responsibility.matches:
            if item.status == "missing" or not item.evidence_text or not item.evidence_type:
                continue
            evidence.append(
                JobMatchEvidence(
                    requirement=item.responsibility,
                    candidate_evidence=item.evidence_text,
                    evidence_source=item.evidence_type,
                    match_type="responsibility_semantic",
                    similarity=item.similarity,
                )
            )
        if career_intent.intent_calculable and career_intent.best_target_role:
            evidence.append(
                JobMatchEvidence(
                    requirement=job_title,
                    candidate_evidence=career_intent.best_target_role,
                    evidence_source="career_intent",
                    match_type="career_intent",
                    similarity=career_intent.intent_similarity,
                )
            )

        level = self._match_level(final_score)
        summary = f"该岗位与你当前画像的匹配度{level}，最终得分为 {final_score:.1f} 分。"
        if highlights:
            summary += highlights[0] + "。"
        return JobMatchRecommendation(
            summary=summary,
            highlights=highlights,
            evidence=evidence,
        )

    @staticmethod
    def _gaps(
        skill: SkillScoreResponse,
        responsibility: ResponsibilityScoreResponse,
        career_intent: CareerIntentScoreResponse,
    ) -> list[JobMatchGap]:
        gaps: list[JobMatchGap] = []
        for item in skill.graph_required_matches:
            gaps.append(
                JobMatchGap(
                    name=item.jd_skill,
                    gap_type="transferable",
                    importance="required",
                    current_evidence=item.candidate_skill,
                    reason=f"没有直接技能证据，但知识图谱识别到相关技能 {item.candidate_skill}。",
                    suggestion="可以说明可迁移能力和学习基础，但不要表述为直接项目经验。",
                )
            )
        for skill_name in skill.missing_required_skills:
            gaps.append(
                JobMatchGap(
                    name=skill_name,
                    gap_type="hard_gap",
                    importance="required",
                    reason="简历技能中没有直接匹配，也没有找到知识图谱关联技能。",
                    suggestion="这是必须技能，应优先补充学习或可验证的实践。",
                )
            )
        for skill_name in skill.missing_preferred_skills:
            gaps.append(
                JobMatchGap(
                    name=skill_name,
                    gap_type="optional_gap",
                    importance="preferred",
                    reason="该加分技能没有匹配，但不影响核心匹配分。",
                    suggestion="时间允许时补充，优先级低于必须技能。",
                )
            )
        for responsibility_text in responsibility.unmatched_responsibilities:
            gaps.append(
                JobMatchGap(
                    name=responsibility_text,
                    gap_type="experience_gap",
                    importance="responsibility",
                    reason="工作、项目和研究经历中没有找到足够相似的证据。",
                    suggestion="检查是否有相关经历尚未写入简历；没有时不要虚构。",
                )
            )
        if career_intent.intent_calculable and career_intent.intent_coverage < 60:
            gaps.append(
                JobMatchGap(
                    name="岗位方向",
                    gap_type="intent_gap",
                    importance="career_intent",
                    current_evidence=career_intent.best_target_role,
                    reason="该岗位与当前求职意向的方向匹配度较低。",
                    suggestion="确认是否愿意扩大目标岗位范围，再决定是否投入准备时间。",
                )
            )
        return gaps

    @staticmethod
    def _match_level(score: float) -> str:
        if score >= 80:
            return "较高"
        if score >= 60:
            return "良好"
        if score >= 40:
            return "一般"
        return "较低"
