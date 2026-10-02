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
    JobImprovementPlan,
    JobImprovementPriority,
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
    ALGORITHM_VERSION = "job-match-detail-v3"

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

        gaps = self._gaps(
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
            improvement_plan=self._improvement_plan(
                gaps,
            ),
            gaps=gaps,
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

        direct_required = self._unique_names(
            item.candidate_skill for item in skill.direct_required_matches
        )
        if direct_required:
            highlights.append(
                f"Your {self._join_names(direct_required)} skills meet required skill expectations."
            )
        if skill.graph_required_matches:
            candidate_skills = self._unique_names(
                item.candidate_skill for item in skill.graph_required_matches
            )
            required_skills = self._unique_names(
                item.jd_skill for item in skill.graph_required_matches
            )
            highlights.append(
                f"Your {self._join_names(candidate_skills)} experience provides a transferable "
                f"foundation for the required {self._join_names(required_skills)} skills."
            )
        if responsibility.responsibilities_calculable:
            evidence_labels = self._responsibility_evidence_labels(
                responsibility
            )
            if evidence_labels:
                highlights.append(
                    f"Your resume evidence from {self._join_names(evidence_labels)} is relevant "
                    "to this role's responsibilities."
                )
        if career_intent.intent_calculable and career_intent.best_target_role:
            highlights.append(self._intent_highlight(career_intent))
        preferred_skills = self._unique_names(
            item.candidate_skill
            for item in [
                *skill.direct_preferred_matches,
                *skill.graph_preferred_matches,
            ]
        )
        if preferred_skills:
            highlights.append(
                f"Your {self._join_names(preferred_skills)} skills align with the role's "
                "preferred skills."
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

        level, level_label, summary = self._match_assessment(final_score)
        return JobMatchRecommendation(
            level=level,
            level_label=level_label,
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
                    reason=(
                        "No direct skill evidence was found, but the knowledge graph identified "
                        f"{item.candidate_skill} as a related skill."
                    ),
                    suggestion=(
                        "Present this as transferable knowledge and a learning foundation, "
                        "not as direct project experience."
                    ),
                )
            )
        for skill_name in skill.missing_required_skills:
            gaps.append(
                JobMatchGap(
                    name=skill_name,
                    gap_type="hard_gap",
                    importance="required",
                    reason="No direct or knowledge-graph-related skill evidence was found in the resume.",
                    suggestion=(
                        "This is a required skill. Prioritize foundational learning and build "
                        "verifiable practical evidence."
                    ),
                )
            )
        for skill_name in skill.missing_preferred_skills:
            gaps.append(
                JobMatchGap(
                    name=skill_name,
                    gap_type="optional_gap",
                    importance="preferred",
                    reason="This preferred skill was not matched, but it does not affect the core match.",
                    suggestion="Consider adding it after the required skills have been addressed.",
                )
            )
        for responsibility_text in responsibility.unmatched_responsibilities:
            gaps.append(
                JobMatchGap(
                    name=responsibility_text,
                    gap_type="experience_gap",
                    importance="responsibility",
                    reason=(
                        "No sufficiently similar evidence was found in the candidate's work, "
                        "project, or research experience."
                    ),
                    suggestion=(
                        "Check whether relevant experience is missing from the resume. "
                        "Do not invent experience that did not occur."
                    ),
                )
            )
        if career_intent.intent_calculable and career_intent.intent_coverage < 60:
            gaps.append(
                JobMatchGap(
                    name="Role direction",
                    gap_type="intent_gap",
                    importance="career_intent",
                    current_evidence=career_intent.best_target_role,
                    reason="This role has limited alignment with the candidate's current target role.",
                    suggestion=(
                        "Confirm whether broadening the target role is acceptable before investing "
                        "significant preparation time."
                    ),
                )
            )
        return gaps

    @classmethod
    def _improvement_plan(cls, gaps: list[JobMatchGap]) -> JobImprovementPlan:
        hard_gaps = [gap for gap in gaps if gap.gap_type == "hard_gap"]
        transferable = [gap for gap in gaps if gap.gap_type == "transferable"]
        experience_gaps = [gap for gap in gaps if gap.gap_type == "experience_gap"]
        optional_gaps = [gap for gap in gaps if gap.gap_type == "optional_gap"]
        intent_gaps = [gap for gap in gaps if gap.gap_type == "intent_gap"]

        summary_parts: list[str] = []
        priorities: list[JobImprovementPriority] = []

        if hard_gaps:
            names = [gap.name for gap in hard_gaps]
            summary_parts.append(
                f"Prioritize the required skills {cls._join_names(names)} and build verifiable "
                "evidence through coursework, personal projects, or internship tasks"
            )
            priorities.append(
                JobImprovementPriority(
                    priority="high",
                    title="Build required skills",
                    items=names,
                    advice=(
                        "Learn the core concepts, then complete a project that demonstrates how "
                        "the skills were applied and what resulted. Do not add keywords without evidence."
                    ),
                )
            )

        if transferable:
            targets = [gap.name for gap in transferable]
            foundations = cls._unique_names(
                gap.current_evidence for gap in transferable
            )
            summary_parts.append(
                f"Your existing {cls._join_names(foundations)} experience provides a transferable "
                f"foundation for {cls._join_names(targets)}. Explain the connection and actual "
                "usage context in the resume without presenting related experience as direct mastery"
            )
            priorities.append(
                JobImprovementPriority(
                    priority="medium",
                    title="Strengthen transferable evidence",
                    items=targets,
                    advice=(
                        f"Use your existing {cls._join_names(foundations)} experience to explain the "
                        "learning foundation, then add direct evidence through a focused practical task."
                    ),
                )
            )

        if experience_gaps:
            responsibilities = [gap.name for gap in experience_gaps]
            summary_parts.append(
                "The resume does not yet provide sufficient evidence for responsibilities such as "
                f"{cls._join_names(responsibilities)}. Review existing projects, internships, and "
                "research for omitted evidence, then describe the technologies used, personal "
                "contribution, and verifiable outcomes"
            )
            priorities.append(
                JobImprovementPriority(
                    priority="high",
                    title="Add responsibility evidence",
                    items=responsibilities,
                    advice=(
                        "Improve existing truthful experience first. If no relevant experience exists, "
                        "build it through a new project rather than inventing evidence."
                    ),
                )
            )

        if optional_gaps:
            names = [gap.name for gap in optional_gaps]
            summary_parts.append(
                f"The preferred skills {cls._join_names(names)} can be addressed after the core "
                "requirements and responsibility evidence are stronger"
            )
            priorities.append(
                JobImprovementPriority(
                    priority="medium",
                    title="Add preferred skills",
                    items=names,
                    advice=(
                        "Address these after the core requirements, prioritizing skills that can be "
                        "integrated into an existing project."
                    ),
                )
            )

        if intent_gaps:
            summary_parts.append(
                "This role differs from your current target direction. Confirm whether you are willing "
                "to broaden the target role before deciding how much preparation time to invest"
            )
            priorities.append(
                JobImprovementPriority(
                    priority="low",
                    title="Confirm role direction",
                    items=[gap.current_evidence or gap.name for gap in intent_gaps],
                    advice=(
                        "Compare the role's day-to-day responsibilities with your longer-term direction "
                        "before beginning focused preparation."
                    ),
                )
            )

        if not summary_parts:
            return JobImprovementPlan(
                summary=(
                    "The resume already covers the role's main requirements. Strengthen measurable "
                    "outcomes and individual contributions to make the existing evidence more persuasive."
                ),
                priorities=[],
                next_action=(
                    "Review each relevant experience and confirm that it clearly states the technologies "
                    "used, individual contribution, and verifiable outcome."
                ),
            )

        if hard_gaps:
            next_action = (
                f"Start with {hard_gaps[0].name}: learn the fundamentals, complete one demonstrable "
                "practical task, and add the truthful process and outcome to the resume."
            )
        elif experience_gaps:
            next_action = (
                f"First check whether existing experience can support '{experience_gaps[0].name}'. "
                "If not, plan a small project that genuinely covers this responsibility."
            )
        elif transferable:
            next_action = (
                f"Complete one direct practical task involving {transferable[0].name}, then accurately "
                "explain how the existing skill transferred to it."
            )
        elif optional_gaps:
            next_action = (
                f"Add {optional_gaps[0].name} to an existing project and produce demonstrable usage evidence."
            )
        else:
            next_action = (
                "Confirm that the role fits the longer-term career direction before continuing preparation."
            )

        return JobImprovementPlan(
            summary="; ".join(summary_parts) + ".",
            priorities=priorities,
            next_action=next_action,
        )

    @staticmethod
    def _match_assessment(score: float) -> tuple[str, str, str]:
        if score >= 80:
            return "excellent", "Excellent match", "This role is an excellent match for your current profile."
        if score >= 60:
            return "strong", "Strong match", "This role is a strong match for your current profile."
        if score >= 40:
            return "moderate", "Moderate match", "Your profile has a useful foundation for this role."
        return (
            "developing",
            "More preparation needed",
            "Additional skills and evidence would strengthen your readiness for this role.",
        )

    @staticmethod
    def _unique_names(names) -> list[str]:
        return list(dict.fromkeys(name.strip() for name in names if name and name.strip()))

    @staticmethod
    def _join_names(names: list[str], limit: int = 3) -> str:
        visible = names[:limit]
        if len(names) > limit:
            return ", ".join(visible) + ", and others"
        if len(visible) == 1:
            return visible[0]
        if len(visible) == 2:
            return " and ".join(visible)
        return ", ".join(visible[:-1]) + f", and {visible[-1]}"

    @classmethod
    def _responsibility_evidence_labels(
        cls,
        responsibility: ResponsibilityScoreResponse,
    ) -> list[str]:
        labels: list[str] = []
        suffixes = {
            "experience": " experience",
            "project": " project",
            "research": " research",
        }
        for item in responsibility.matches:
            if item.status == "missing" or not item.evidence_title or not item.evidence_type:
                continue
            labels.append(f"{item.evidence_title}{suffixes[item.evidence_type]}")
        return cls._unique_names(labels)

    @staticmethod
    def _intent_highlight(career_intent: CareerIntentScoreResponse) -> str:
        role = career_intent.best_target_role
        if career_intent.intent_coverage >= 75:
            return f"This role is strongly aligned with your target role: {role}."
        if career_intent.intent_coverage >= 50:
            return f"This role has some alignment with your target role: {role}."
        return f"This role has limited alignment with your target role: {role}."
