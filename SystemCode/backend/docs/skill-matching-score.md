# Skill Matching Score

This module implements the skill-based part of the IT CareerPilot matching score.
It does not yet include responsibility similarity or career-intent fit, so the
returned `partial_score` has a maximum of 65 points.

## Input

- Candidate skills come only from `candidate.skills` in the formatted resume.
- Required skills come from `job.required_skills` in the structured JD.
- Preferred skills come from `job.preferred_skills` in the structured JD.
- Skill names are normalized with the shared alias lexicon and the MIND ontology.

## Formula

```text
required_direct_points = 0.40 * required_direct_coverage
required_graph_points = 0.20 * required_graph_coverage

preferred_skill_coverage =
    0.70 * preferred_direct_coverage
  + 0.30 * preferred_graph_coverage

preferred_bonus = 0.05 * preferred_skill_coverage

partial_score =
    required_direct_points
  + required_graph_points
  + preferred_bonus
```

Coverage values use a 0-100 scale. Point values use the final score scale.

For graph coverage, a directly matched skill contributes `1.0`. An unmatched JD
skill is compared with every candidate skill, and only the highest-scoring graph
relationship is retained.

## Graph relationship weights

| Relationship | Score |
|---|---:|
| One-hop implication | 0.8 |
| Same type and domain with a shared foundation | 0.6 |
| Two-hop implication | 0.3 |
| Required skill builds on the candidate skill | 0.3 |
| Same type and technical domain only | 0.1 |
| No supported relationship | 0.0 |

Graph traversal is limited to two hops. Direct matches do not produce a second
graph-match record, but they count as fully covered in graph coverage.

## API

```http
POST /api/matches/skills
Content-Type: application/json
```

```json
{
  "candidate": {
    "name": "Jane Tan",
    "skills": ["Python", "FastAPI", "Docker"]
  },
  "job": {
    "job_id": 1,
    "company": "Acme",
    "title": "Backend Engineer",
    "required_skills": ["python", "sql", "kubernetes"],
    "preferred_skills": ["fastapi", "aws"]
  }
}
```

The response includes component coverage, weighted points, direct matches, graph
matches with paths, and skills for which no supported match was found.
