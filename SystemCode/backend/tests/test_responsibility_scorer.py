import math

from app.matching.responsibility_scorer import ResponsibilityScorer
from app.schemas.job import JobRequirementDocument
from app.schemas.resume import Experience, Project, Research, ResumeDocument


class FakeEmbeddingProvider:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors
        self.calls: list[list[str]] = []

    def encode(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [self.vectors[text] for text in texts]


def _job(responsibilities: list[str]) -> JobRequirementDocument:
    return JobRequirementDocument(
        job_id=1,
        company="Acme",
        title="Backend Engineer",
        responsibilities=responsibilities,
    )


def test_each_responsibility_uses_its_best_resume_evidence() -> None:
    experience_text = "Experience: Backend Intern. Built and maintained REST APIs."
    project_text = (
        "Project: Deployment Platform. Role: Developer. Automated cloud deployments. "
        "Technologies: Docker, AWS."
    )
    provider = FakeEmbeddingProvider(
        {
            "Develop backend APIs": [1.0, 0.0],
            "Automate cloud deployments": [0.0, 1.0],
            experience_text: [1.0, 0.0],
            project_text: [0.0, 1.0],
        }
    )
    scorer = ResponsibilityScorer(provider)
    candidate = ResumeDocument(
        experiences=[
            Experience(
                company="Acme",
                title="Backend Intern",
                description="Built and maintained REST APIs.",
            )
        ],
        projects=[
            Project(
                title="Deployment Platform",
                role="Developer",
                summary="Automated cloud deployments.",
                technologies=["Docker", "AWS"],
            )
        ],
    )

    result = scorer.score(
        candidate,
        _job(["Develop backend APIs", "Automate cloud deployments"]),
    )

    assert result.responsibilities_calculable is True
    assert result.resume_evidence_available is True
    assert result.responsibility_coverage == 100.0
    assert result.responsibility_points == 30.0
    assert [match.evidence_type for match in result.matches] == [
        "experience",
        "project",
    ]
    assert [match.status for match in result.matches] == ["matched", "matched"]
    assert result.unmatched_responsibilities == []


def test_similarity_between_thresholds_is_linearly_mapped() -> None:
    evidence_text = "Experience: Developer. Implemented internal tools."
    provider = FakeEmbeddingProvider(
        {
            "Build customer-facing services": [1.0, 0.0],
            evidence_text: [0.55, math.sqrt(1 - 0.55**2)],
        }
    )
    scorer = ResponsibilityScorer(provider)

    result = scorer.score(
        ResumeDocument(
            experiences=[
                Experience(
                    company="Acme",
                    title="Developer",
                    description="Implemented internal tools.",
                )
            ]
        ),
        _job(["Build customer-facing services"]),
    )

    assert result.responsibility_coverage == 50.0
    assert result.responsibility_points == 15.0
    assert result.matches[0].similarity == 0.55
    assert result.matches[0].status == "partial"


def test_no_job_responsibilities_is_not_calculable() -> None:
    provider = FakeEmbeddingProvider({})
    result = ResponsibilityScorer(provider).score(
        ResumeDocument(), _job(["", "  "])
    )

    assert result.responsibilities_calculable is False
    assert result.responsibility_count == 0
    assert result.responsibility_points == 0
    assert provider.calls == []


def test_job_responsibilities_with_no_resume_evidence_score_zero() -> None:
    provider = FakeEmbeddingProvider({})
    result = ResponsibilityScorer(provider).score(
        ResumeDocument(
            experiences=[Experience(company="Acme", title="Intern", description="")],
            projects=[Project(title="Empty project")],
        ),
        _job(["Build APIs", "Write automated tests"]),
    )

    assert result.responsibilities_calculable is True
    assert result.resume_evidence_available is False
    assert result.evidence_count == 0
    assert result.responsibility_coverage == 0
    assert result.responsibility_points == 0
    assert result.unmatched_responsibilities == ["Build APIs", "Write automated tests"]
    assert all(match.status == "missing" for match in result.matches)
    assert provider.calls == []


def test_duplicate_responsibilities_are_scored_once_and_embeddings_are_cached() -> None:
    evidence_text = "Experience: Engineer. Built APIs."
    provider = FakeEmbeddingProvider(
        {
            "Build APIs": [1.0, 0.0],
            evidence_text: [1.0, 0.0],
        }
    )
    scorer = ResponsibilityScorer(provider)
    candidate = ResumeDocument(
        experiences=[
            Experience(company="Acme", title="Engineer", description="Built APIs.")
        ]
    )
    job = _job([" Build APIs ", "build APIs"])

    first = scorer.score(candidate, job)
    second = scorer.score(candidate, job)

    assert first.responsibility_count == 1
    assert second.responsibility_count == 1
    assert provider.calls.count(["Build APIs"]) == 1


def test_prepared_resume_evidence_is_reused_across_jobs() -> None:
    evidence_text = "Experience: Engineer. Built APIs."
    provider = FakeEmbeddingProvider(
        {
            "Build APIs": [1.0, 0.0],
            "Design services": [1.0, 0.0],
            evidence_text: [1.0, 0.0],
        }
    )
    scorer = ResponsibilityScorer(provider)
    candidate = ResumeDocument(
        experiences=[
            Experience(company="Acme", title="Engineer", description="Built APIs.")
        ]
    )
    prepared = scorer.prepare_candidate(candidate)

    scorer.score(candidate, _job(["Build APIs"]), prepared_evidence=prepared)
    scorer.score(candidate, _job(["Design services"]), prepared_evidence=prepared)

    assert provider.calls.count([evidence_text]) == 1


def test_research_summary_can_be_the_best_evidence() -> None:
    research_text = (
        "Research: Fraud Detection. Studied anomaly detection for transaction streams."
    )
    provider = FakeEmbeddingProvider(
        {
            "Research transaction anomaly detection": [1.0, 0.0],
            research_text: [1.0, 0.0],
        }
    )
    result = ResponsibilityScorer(provider).score(
        ResumeDocument(
            research=[
                Research(
                    title="Fraud Detection",
                    summary="Studied anomaly detection for transaction streams.",
                )
            ]
        ),
        _job(["Research transaction anomaly detection"]),
    )

    assert result.matches[0].evidence_type == "research"
    assert result.matches[0].evidence_index == 0
    assert result.responsibility_points == 30.0
