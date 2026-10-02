from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import math
import random
import secrets

from app.repositories.interview_recommendation_repository import (
    InterviewCandidateQuestion,
    InterviewRecommendationRepository,
    InterviewRoleMatch,
)
from app.schemas.interview_question import GENERAL_PROGRAMMING_ROLE
from app.schemas.interview_recommendation import (
    DifficultyMix,
    InterviewQuestionSampleRequest,
    InterviewQuestionSampleResponse,
    InterviewRoleAllocation,
    SampledInterviewQuestion,
)


DIFFICULTIES = ("easy", "medium", "hard")


class InterviewJobNotFoundError(LookupError):
    pass


class InterviewRoleMatchesUnavailableError(RuntimeError):
    pass


class InterviewQuestionRecommendationService:
    def __init__(
        self,
        repository: InterviewRecommendationRepository | None = None,
    ) -> None:
        self.repository = repository or InterviewRecommendationRepository()

    def sample(
        self,
        job_id: int,
        request: InterviewQuestionSampleRequest,
    ) -> InterviewQuestionSampleResponse:
        job = self.repository.get_job_context(job_id)
        if job is None:
            raise InterviewJobNotFoundError(f"Job {job_id} was not found.")

        role_matches = self.repository.list_role_matches(job_id, limit=3)
        if not role_matches:
            raise InterviewRoleMatchesUnavailableError(
                f"Job {job_id} has no stored standard-role matches."
            )

        seed = request.seed if request.seed is not None else secrets.randbits(63)
        rng = random.Random(seed)
        difficulty_targets = self._difficulty_targets(request)
        basic_target = 2 if request.count <= 7 else 3
        basic_difficulties = self._reserve_basic_difficulties(
            difficulty_targets,
            basic_target,
        )
        role_difficulties = Counter(difficulty_targets)
        for difficulty in basic_difficulties:
            role_difficulties[difficulty] -= 1

        role_count = request.count - basic_target
        normalized_weights = self._normalized_weights(role_matches)
        role_quotas = self._largest_remainder(
            [normalized_weights[item.role] for item in role_matches],
            role_count,
        )

        candidate_roles = [item.role for item in role_matches] + [GENERAL_PROGRAMMING_ROLE]
        candidates = self.repository.list_candidates(
            candidate_roles,
            request.exclude_question_ids,
        )
        selected: list[tuple[InterviewCandidateQuestion, str, str]] = []
        selected_ids: set[int] = set()
        warnings: list[str] = []

        basic_pool = [
            item for item in candidates if GENERAL_PROGRAMMING_ROLE in item.roles
        ]
        role_pools = self._assign_role_candidates(candidates, role_matches)

        for difficulty in basic_difficulties:
            question = self._take_question(
                basic_pool,
                selected_ids,
                difficulty,
                rng,
            )
            if question is None:
                question = self._take_question(basic_pool, selected_ids, None, rng)
                self._add_warning(
                    warnings,
                    f"Not enough {difficulty} basic programming questions; another difficulty was used.",
                )
            if question is not None:
                selected.append((question, "basic_programming", GENERAL_PROGRAMMING_ROLE))
                selected_ids.add(question.id)

        role_slots = [
            role_matches[index].role
            for index, quota in enumerate(role_quotas)
            for _ in range(quota)
        ]
        difficulty_slots = [
            difficulty
            for difficulty in DIFFICULTIES
            for _ in range(max(0, role_difficulties[difficulty]))
        ]
        rng.shuffle(role_slots)
        rng.shuffle(difficulty_slots)

        for requested_role, difficulty in zip(role_slots, difficulty_slots, strict=True):
            question, allocated_role = self._take_role_question(
                role_pools,
                requested_role,
                difficulty,
                selected_ids,
                rng,
            )
            if question is None:
                question = self._take_question(basic_pool, selected_ids, difficulty, rng)
                if question is None:
                    question = self._take_question(basic_pool, selected_ids, None, rng)
                allocated_role = GENERAL_PROGRAMMING_ROLE
                self._add_warning(
                    warnings,
                    "Role-specific questions were insufficient; basic programming questions were used.",
                )
            elif allocated_role != requested_role:
                self._add_warning(
                    warnings,
                    "A role quota was redistributed because its candidate pool was insufficient.",
                )
            if question is None:
                self._add_warning(
                    warnings,
                    "The available question bank could not satisfy the requested count.",
                )
                continue
            selected.append(
                (
                    question,
                    "basic_programming"
                    if allocated_role == GENERAL_PROGRAMMING_ROLE
                    else "role_specific",
                    allocated_role,
                )
            )
            selected_ids.add(question.id)

        rng.shuffle(selected)
        actual_role_counts = Counter(
            allocated_role
            for _, question_type, allocated_role in selected
            if question_type == "role_specific"
        )
        actual_difficulties = Counter(question.difficulty_level for question, _, _ in selected)
        response_questions = [
            SampledInterviewQuestion(
                sequence=index,
                id=question.id,
                question_type=question_type,
                allocated_role=allocated_role,
                question_text=question.question_text,
                standard_answer=question.standard_answer,
                question_text_en=question.question_text_en,
                standard_answer_en=question.standard_answer_en,
                difficulty_level=question.difficulty_level,
                roles=list(question.roles),
                source=question.source,
                company=question.company,
            )
            for index, (question, question_type, allocated_role) in enumerate(selected, start=1)
        ]
        allocations = [
            InterviewRoleAllocation(
                role=item.role,
                similarity=round(item.similarity, 4),
                normalized_weight=round(normalized_weights[item.role], 4),
                requested_quota=role_quotas[index],
                actual_count=actual_role_counts[item.role],
            )
            for index, item in enumerate(role_matches)
        ]
        return InterviewQuestionSampleResponse(
            job_id=job.job_id,
            job_title=job.title,
            seed=seed,
            generated_at=datetime.now(timezone.utc),
            requested_count=request.count,
            returned_count=len(response_questions),
            role_allocation=allocations,
            basic_question_count=sum(
                item.question_type == "basic_programming" for item in response_questions
            ),
            difficulty_distribution=DifficultyMix(
                easy=actual_difficulties["easy"],
                medium=actual_difficulties["medium"],
                hard=actual_difficulties["hard"],
            ),
            questions=response_questions,
            warnings=warnings,
        )

    @staticmethod
    def _difficulty_targets(request: InterviewQuestionSampleRequest) -> Counter[str]:
        if request.difficulty_mix is not None:
            return Counter(request.difficulty_mix.model_dump())
        quotas = InterviewQuestionRecommendationService._largest_remainder(
            [0.4, 0.4, 0.2],
            request.count,
        )
        return Counter(dict(zip(DIFFICULTIES, quotas, strict=True)))

    @staticmethod
    def _reserve_basic_difficulties(
        targets: Counter[str],
        basic_count: int,
    ) -> list[str]:
        reserved: list[str] = []
        remaining = Counter(targets)
        for difficulty in DIFFICULTIES:
            if len(reserved) == basic_count:
                break
            if remaining[difficulty] > 0:
                reserved.append(difficulty)
                remaining[difficulty] -= 1
        while len(reserved) < basic_count:
            available = max(DIFFICULTIES, key=lambda item: remaining[item])
            if remaining[available] <= 0:
                break
            reserved.append(available)
            remaining[available] -= 1
        return reserved

    @staticmethod
    def _normalized_weights(role_matches: list[InterviewRoleMatch]) -> dict[str, float]:
        non_negative = [max(0.0, item.similarity) for item in role_matches]
        total = sum(non_negative)
        if total <= 0:
            equal = 1 / len(role_matches)
            return {item.role: equal for item in role_matches}
        return {
            item.role: non_negative[index] / total
            for index, item in enumerate(role_matches)
        }

    @staticmethod
    def _largest_remainder(weights: list[float], total: int) -> list[int]:
        if not weights:
            return []
        weight_sum = sum(weights)
        normalized = [item / weight_sum for item in weights] if weight_sum else [1 / len(weights)] * len(weights)
        raw = [item * total for item in normalized]
        quotas = [math.floor(item) for item in raw]
        remaining = total - sum(quotas)
        order = sorted(
            range(len(weights)),
            key=lambda index: (-(raw[index] - quotas[index]), index),
        )
        for index in order[:remaining]:
            quotas[index] += 1
        return quotas

    @staticmethod
    def _assign_role_candidates(
        candidates: list[InterviewCandidateQuestion],
        role_matches: list[InterviewRoleMatch],
    ) -> dict[str, list[InterviewCandidateQuestion]]:
        score_by_role = {item.role: item.similarity for item in role_matches}
        rank_by_role = {item.role: item.rank for item in role_matches}
        pools = {item.role: [] for item in role_matches}
        for question in candidates:
            matched_roles = [role for role in question.roles if role in score_by_role]
            if not matched_roles:
                continue
            allocated_role = max(
                matched_roles,
                key=lambda role: (score_by_role[role], -rank_by_role[role]),
            )
            pools[allocated_role].append(question)
        return pools

    @staticmethod
    def _take_question(
        pool: list[InterviewCandidateQuestion],
        selected_ids: set[int],
        difficulty: str | None,
        rng: random.Random,
    ) -> InterviewCandidateQuestion | None:
        choices = [
            item
            for item in pool
            if item.id not in selected_ids
            and (difficulty is None or item.difficulty_level == difficulty)
        ]
        return rng.choice(choices) if choices else None

    def _take_role_question(
        self,
        pools: dict[str, list[InterviewCandidateQuestion]],
        requested_role: str,
        difficulty: str,
        selected_ids: set[int],
        rng: random.Random,
    ) -> tuple[InterviewCandidateQuestion | None, str]:
        question = self._take_question(
            pools.get(requested_role, []), selected_ids, difficulty, rng
        )
        if question is not None:
            return question, requested_role
        question = self._take_question(
            pools.get(requested_role, []), selected_ids, None, rng
        )
        if question is not None:
            return question, requested_role
        for role, pool in pools.items():
            if role == requested_role:
                continue
            question = self._take_question(pool, selected_ids, difficulty, rng)
            if question is not None:
                return question, role
        for role, pool in pools.items():
            if role == requested_role:
                continue
            question = self._take_question(pool, selected_ids, None, rng)
            if question is not None:
                return question, role
        return None, requested_role

    @staticmethod
    def _add_warning(warnings: list[str], warning: str) -> None:
        if warning not in warnings:
            warnings.append(warning)
