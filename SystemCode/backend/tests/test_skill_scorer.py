from app.matching.skill_scorer import SkillScorer
from app.schemas.job import JobRequirementDocument
from app.schemas.resume import ResumeDocument


def _job(
    required_skills: list[str],
    preferred_skills: list[str] | None = None,
) -> JobRequirementDocument:
    return JobRequirementDocument(
        job_id=1,
        company="Acme",
        title="Backend Engineer",
        required_skills=required_skills,
        preferred_skills=preferred_skills or [],
    )


def test_skill_scorer_combines_direct_graph_and_preferred_bonus() -> None:
    candidate = ResumeDocument(
        skills=["Python", "Next.js", "FastAPI", "MySQL", "Docker"]
    )

    result = SkillScorer().score(
        candidate,
        _job(
            required_skills=["python", "react", "sql", "kubernetes"],
            preferred_skills=["flask", "postgresql", "aws"],
        ),
    )

    assert result.required_direct_coverage == 25.0
    assert result.required_direct_points == 5.0
    assert result.required_graph_coverage == 47.5
    assert result.required_graph_points == 9.5
    assert result.preferred_direct_coverage == 0.0
    assert result.preferred_graph_coverage == 40.0
    assert result.preferred_skill_coverage == 12.0
    assert result.preferred_bonus == 0.6
    assert result.partial_score == 15.1
    assert result.missing_required_skills == []
    assert result.missing_preferred_skills == ["aws"]

    graph_matches = {
        match.jd_skill: match for match in result.graph_required_matches
    }
    assert graph_matches["react"].candidate_skill == "Next.js"
    assert graph_matches["react"].relation_score == 0.8
    assert graph_matches["sql"].path == ["MySQL", "SQL"]
    assert graph_matches["kubernetes"].relation_score == 0.3


def test_skill_aliases_are_direct_matches_and_are_not_counted_twice() -> None:
    candidate = ResumeDocument(skills=["React.js", "Amazon Web Services", "AWS"])

    result = SkillScorer().score(
        candidate,
        _job(required_skills=["react"], preferred_skills=["aws"]),
    )

    assert result.required_direct_coverage == 100.0
    assert result.required_graph_coverage == 0.0
    assert result.required_direct_points == 20.0
    assert result.required_graph_points == 0.0
    assert len(result.direct_required_matches) == 1
    assert result.graph_required_matches == []
    assert len(result.direct_preferred_matches) == 1
    assert result.preferred_skill_coverage == 100.0
    assert result.preferred_bonus == 5.0
    assert result.partial_score == 25.0


def test_one_candidate_skill_can_support_multiple_jd_skills_with_separate_paths() -> None:
    result = SkillScorer().score(
        ResumeDocument(skills=["Next.js"]),
        _job(required_skills=["react", "javascript"]),
    )

    assert result.required_direct_coverage == 0.0
    assert result.required_graph_coverage == 80.0
    assert {match.jd_skill for match in result.graph_required_matches} == {
        "react",
        "javascript",
    }
    assert all(
        match.candidate_skill == "Next.js"
        for match in result.graph_required_matches
    )


def test_react_agent_paradigm_does_not_match_react_framework() -> None:
    result = SkillScorer().score(ResumeDocument(skills=["ReAct", "Python"]), _job(required_skills=["react", "python"]))

    assert [match.jd_skill for match in result.direct_required_matches] == ["python"]
    assert all(match.candidate_skill != "ReAct" for match in result.graph_required_matches)


def test_no_preferred_skills_means_no_bonus_and_no_penalty() -> None:
    result = SkillScorer().score(
        ResumeDocument(skills=["Python"]),
        _job(required_skills=["python"]),
    )

    assert result.preferred_skills_available is False
    assert result.preferred_direct_coverage == 0.0
    assert result.preferred_graph_coverage == 0.0
    assert result.preferred_skill_coverage == 0.0
    assert result.preferred_bonus == 0.0
    assert result.partial_score == 20.0


def test_empty_required_skills_are_reported_as_not_calculable() -> None:
    result = SkillScorer().score(
        ResumeDocument(skills=["Python"]),
        _job(required_skills=["", " "], preferred_skills=["python"]),
    )

    assert result.required_skills_calculable is False
    assert result.required_direct_points == 0.0
    assert result.required_graph_points == 0.0
    assert result.preferred_bonus == 5.0
    assert result.partial_score == 5.0


def test_agent_frameworks_imply_agentic_ai_skills() -> None:
    result = SkillScorer().score(
        ResumeDocument(skills=["LangGraph", "MCP"]),
        _job(required_skills=["AI Agents", "Tool Calling"]),
    )

    assert result.required_direct_coverage == 0.0
    assert result.required_graph_coverage == 80.0
    assert result.missing_required_skills == []
    assert all(
        match.relation == "one_hop_implication"
        for match in result.graph_required_matches
    )


def test_shared_agent_application_domain_is_a_weak_relationship() -> None:
    result = SkillScorer().score(
        ResumeDocument(skills=["AI Evaluation"]),
        _job(required_skills=["MCP"]),
    )

    assert result.required_graph_coverage == 20.0
    assert result.graph_required_matches[0].relation == "same_application_domain"
    assert result.graph_required_matches[0].relation_score == 0.2
