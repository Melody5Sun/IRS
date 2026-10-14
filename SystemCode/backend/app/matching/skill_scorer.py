from dataclasses import dataclass

from app.knowledge.mind_ontology import MindKnowledgeGraph, MindSkill, get_mind_knowledge_graph
from app.parsers.text_parser import find_skill_matches
from app.schemas.job import JobRequirementDocument
from app.schemas.match import DirectSkillMatch, GraphSkillMatch, SkillScoreResponse
from app.schemas.resume import ResumeDocument


@dataclass(frozen=True)
class _NormalizedSkill:
    original: str
    key: str
    graph_skill: MindSkill | None


@dataclass(frozen=True)
class _SkillGroupResult:
    skill_count: int
    direct_coverage: float
    expanded_coverage: float
    direct_matches: list[DirectSkillMatch]
    graph_matches: list[GraphSkillMatch]
    missing_skills: list[str]


class SkillScorer:
    def __init__(self, graph: MindKnowledgeGraph | None = None) -> None:
        self.graph = graph or get_mind_knowledge_graph()

    def score(
        self,
        candidate: ResumeDocument,
        job: JobRequirementDocument,
    ) -> SkillScoreResponse:
        candidate_skills = self._normalize_unique(candidate.skills)
        required = self._score_group(candidate_skills, job.required_skills)
        preferred = self._score_group(candidate_skills, job.preferred_skills)

        required_direct_points = 0.20 * required.direct_coverage
        required_graph_points = 0.20 * required.expanded_coverage
        preferred_skill_coverage = min(
            100.0,
            preferred.direct_coverage + 0.30 * preferred.expanded_coverage,
        )
        preferred_bonus = 0.05 * preferred_skill_coverage

        return SkillScoreResponse(
            job_id=job.job_id,
            required_skills_calculable=required.skill_count > 0,
            preferred_skills_available=preferred.skill_count > 0,
            required_direct_coverage=self._round(required.direct_coverage),
            required_direct_points=self._round(required_direct_points),
            required_graph_coverage=self._round(required.expanded_coverage),
            required_graph_points=self._round(required_graph_points),
            preferred_direct_coverage=self._round(preferred.direct_coverage),
            preferred_graph_coverage=self._round(preferred.expanded_coverage),
            preferred_skill_coverage=self._round(preferred_skill_coverage),
            preferred_bonus=self._round(preferred_bonus),
            partial_score=self._round(
                required_direct_points + required_graph_points + preferred_bonus
            ),
            direct_required_matches=required.direct_matches,
            graph_required_matches=required.graph_matches,
            missing_required_skills=required.missing_skills,
            direct_preferred_matches=preferred.direct_matches,
            graph_preferred_matches=preferred.graph_matches,
            missing_preferred_skills=preferred.missing_skills,
        )

    def _score_group(
        self,
        candidate_skills: list[_NormalizedSkill],
        jd_skill_names: list[str],
    ) -> _SkillGroupResult:
        jd_skills = self._normalize_unique(jd_skill_names)
        if not jd_skills:
            return _SkillGroupResult(0, 0, 0, [], [], [])

        candidate_by_key = {skill.key: skill for skill in candidate_skills}
        direct_matches: list[DirectSkillMatch] = []
        graph_matches: list[GraphSkillMatch] = []
        missing_skills: list[str] = []
        expanded_total = 0.0

        for jd_skill in jd_skills:
            direct_candidate = candidate_by_key.get(jd_skill.key)
            if direct_candidate is not None:
                direct_matches.append(
                    DirectSkillMatch(
                        jd_skill=jd_skill.original,
                        candidate_skill=direct_candidate.original,
                    )
                )
                continue

            graph_match = self._best_graph_match(candidate_skills, jd_skill)
            if graph_match is None:
                missing_skills.append(jd_skill.original)
                continue

            graph_matches.append(graph_match)
            expanded_total += graph_match.relation_score

        count = len(jd_skills)
        return _SkillGroupResult(
            skill_count=count,
            direct_coverage=100 * len(direct_matches) / count,
            expanded_coverage=100 * expanded_total / count,
            direct_matches=direct_matches,
            graph_matches=graph_matches,
            missing_skills=missing_skills,
        )

    def _best_graph_match(
        self,
        candidate_skills: list[_NormalizedSkill],
        jd_skill: _NormalizedSkill,
    ) -> GraphSkillMatch | None:
        if jd_skill.graph_skill is None:
            return None

        matches = [
            match
            for candidate_skill in candidate_skills
            if (
                match := self._graph_match(candidate_skill, jd_skill)
            ) is not None
        ]
        if not matches:
            return None
        return max(
            matches,
            key=lambda match: (
                match.relation_score,
                -len(match.path),
                match.candidate_skill.casefold(),
            ),
        )

    def _graph_match(
        self,
        candidate: _NormalizedSkill,
        target: _NormalizedSkill,
    ) -> GraphSkillMatch | None:
        source_skill = candidate.graph_skill
        target_skill = target.graph_skill
        if source_skill is None or target_skill is None:
            return None

        source_implied = self._resolved_implied(source_skill)
        target_key = self._key(target_skill.name)
        if target_key in source_implied:
            return self._make_graph_match(
                candidate,
                target,
                relation="one_hop_implication",
                score=0.8,
                path=[source_skill.name, target_skill.name],
            )

        shared_foundations = set(source_implied) & set(self._resolved_implied(target_skill))
        same_type = bool(set(source_skill.types) & set(target_skill.types))
        same_domain = bool(
            set(source_skill.relations.get("technicalDomains", ()))
            & set(target_skill.relations.get("technicalDomains", ()))
        )
        same_application_domain = bool(
            set(source_skill.relations.get("associatedToApplicationDomains", ()))
            & set(target_skill.relations.get("associatedToApplicationDomains", ()))
        )
        if same_type and same_domain and shared_foundations:
            shared_skill = max(
                (source_implied[key] for key in shared_foundations),
                key=self._foundation_priority,
            )
            return self._make_graph_match(
                candidate,
                target,
                relation="shared_foundations",
                score=0.6,
                path=[source_skill.name, shared_skill.name, target_skill.name],
            )

        two_hop_path = self._two_hop_path(source_skill, target_key)
        if two_hop_path is not None:
            return self._make_graph_match(
                candidate,
                target,
                relation="two_hop_implication",
                score=0.3,
                path=two_hop_path,
            )

        target_implied = self._resolved_implied(target_skill)
        if self._key(source_skill.name) in target_implied:
            return self._make_graph_match(
                candidate,
                target,
                relation="required_skill_builds_on_candidate_skill",
                score=0.3,
                path=[source_skill.name, target_skill.name],
            )

        if same_application_domain:
            return self._make_graph_match(
                candidate,
                target,
                relation="same_application_domain",
                score=0.2,
                path=[source_skill.name, target_skill.name],
            )

        if same_type and same_domain:
            return self._make_graph_match(
                candidate,
                target,
                relation="same_technical_domain",
                score=0.1,
                path=[source_skill.name, target_skill.name],
            )
        return None

    def _two_hop_path(self, source: MindSkill, target_key: str) -> list[str] | None:
        for intermediate in self._resolved_implied(source).values():
            if target_key in self._resolved_implied(intermediate):
                return [source.name, intermediate.name, self.graph.get_skill(target_key).name]
        return None

    def _resolved_implied(self, skill: MindSkill) -> dict[str, MindSkill]:
        resolved: dict[str, MindSkill] = {}
        for related_name in skill.relations.get("impliesKnowingSkills", ()):
            related = self.graph.get_skill(related_name)
            if related is not None:
                resolved[self._key(related.name)] = related
        return resolved

    def _normalize_unique(self, skill_names: list[str]) -> list[_NormalizedSkill]:
        normalized: dict[str, _NormalizedSkill] = {}
        for raw_name in skill_names:
            clean_name = raw_name.strip()
            if not clean_name:
                continue
            graph_skill = self.graph.get_skill(clean_name)
            canonical_name = graph_skill.name if graph_skill is not None else self._lexicon_name(clean_name)
            key = self._key(canonical_name)
            normalized.setdefault(
                key,
                _NormalizedSkill(
                    original=clean_name,
                    key=key,
                    graph_skill=graph_skill or self.graph.get_skill(canonical_name),
                ),
            )
        return list(normalized.values())

    @staticmethod
    def _lexicon_name(skill_name: str) -> str:
        matches = find_skill_matches(skill_name)
        return matches[0][0] if len(matches) == 1 else skill_name

    @staticmethod
    def _make_graph_match(
        candidate: _NormalizedSkill,
        target: _NormalizedSkill,
        relation: str,
        score: float,
        path: list[str],
    ) -> GraphSkillMatch:
        return GraphSkillMatch(
            jd_skill=target.original,
            candidate_skill=candidate.original,
            relation=relation,
            relation_score=score,
            path=path,
        )

    @staticmethod
    def _key(value: str) -> str:
        return value.strip().casefold()

    @staticmethod
    def _foundation_priority(skill: MindSkill) -> tuple[int, str]:
        preferred_types = {"ProgrammingLanguage", "QueryLanguage"}
        return (bool(preferred_types & set(skill.types)), skill.name.casefold())

    @staticmethod
    def _round(value: float) -> float:
        return round(value + 1e-12, 2)
