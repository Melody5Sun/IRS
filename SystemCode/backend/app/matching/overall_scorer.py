from app.schemas.match import (
    CareerIntentScoreResponse,
    ResponsibilityScoreResponse,
    SkillScoreResponse,
)
from app.schemas.ranking import OverallScore


class OverallScorer:
    """Calculate professional fit; career intent is used only by ranking tiers."""

    COMPONENT_WEIGHTS = {
        "required_direct": 20.0,
        "responsibility": 60.0,
        "required_graph": 20.0,
    }
    def combine(
        self,
        skill: SkillScoreResponse,
        responsibility: ResponsibilityScoreResponse,
        career_intent: CareerIntentScoreResponse,
    ) -> OverallScore:
        coverages: dict[str, float] = {}
        if skill.required_skills_calculable:
            coverages["required_direct"] = skill.required_direct_coverage
            coverages["required_graph"] = skill.required_graph_coverage
        if responsibility.responsibilities_calculable:
            coverages["responsibility"] = responsibility.responsibility_coverage
        active_weight = sum(self.COMPONENT_WEIGHTS[name] for name in coverages)
        if not active_weight:
            return OverallScore(
                calculable=False,
                active_core_weight=0,
                core_score=0,
                preferred_bonus=0,
                professional_score=0,
                intent_fit=(
                    career_intent.intent_coverage
                    if career_intent.intent_calculable
                    else None
                ),
                final_score=0,
            )

        effective_weights = {
            name: self.COMPONENT_WEIGHTS[name] / active_weight
            for name in coverages
        }
        contributions = {
            name: coverages[name] * effective_weights[name]
            for name in coverages
        }
        core_score = sum(contributions.values())
        preferred_bonus = skill.preferred_bonus
        professional_score = min(100.0, core_score + preferred_bonus)
        return OverallScore(
            calculable=True,
            active_core_weight=self._round(active_weight),
            effective_weights={
                name: self._round(weight, 4)
                for name, weight in effective_weights.items()
            },
            normalized_contributions={
                name: self._round(points)
                for name, points in contributions.items()
            },
            core_score=self._round(core_score),
            preferred_bonus=self._round(preferred_bonus),
            professional_score=self._round(professional_score),
            intent_fit=(
                self._round(career_intent.intent_coverage)
                if career_intent.intent_calculable
                else None
            ),
            final_score=self._round(professional_score),
        )

    @staticmethod
    def _round(value: float, digits: int = 2) -> float:
        return round(value + 1e-12, digits)
