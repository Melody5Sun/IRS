# Job ranking weight evaluation

This evaluation tunes the three professional-fit ranking weights against relevance labels.
It does not modify production weights automatically.

## Dataset

- Ten anonymized resumes are configured in `profiles.json`.
- Each resume contributes 20 jobs that already passed production hard constraints.
- Sampling is stratified across four baseline-score quartiles so the annotation set contains strong, borderline, and weak matches.
- The first seven resumes form the validation split. The final three resumes form the held-out test split. Splitting by resume prevents the same candidate from appearing in both sets.
- `annotation_pairs_ai_labeled_professional_v2.csv` is the single final annotation file. It contains all 200 reviewed labels and is grouped by resume.
- `pair_features.jsonl` contains the production component coverages used by the optimizer. Annotators should not inspect this file before labeling.

Target roles are excluded from professional-fit labels. They are evaluated separately and rerank jobs only within the same professional recommendation level.

## Generate the annotation set

Start PostgreSQL, activate the backend environment, and run from `SystemCode/backend`:

```powershell
python scripts/generate_ranking_annotation_set.py
```

The command can regenerate exactly 200 candidate pairs from the database:

- `evaluation/job_ranking/annotation_pairs.csv` (a temporary unlabelled draft)
- `evaluation/job_ranking/pair_features.jsonl`

Generation is deterministic for the same database, profile configuration, and seed.

## Annotation protocol

Label every pair using the resume PDF and JD information in the file. Consider direct skills, related or transferable skills, and relevant experience. Do not use the candidate's target role when assigning professional-fit relevance.

| Label | Meaning |
|---|---|
| 0 | Not suitable. There is almost no meaningful overlap in core skills, transferable skills, or relevant experience. |
| 1 | Weak match. Some transferable evidence exists, but major gaps remain. |
| 2 | Suitable. The candidate has credible evidence for most important requirements. |
| 3 | Strong match. The role closely matches the candidate's direct and related skills and relevant experience. |

Fill the `label` column with an integer from 0 to 3. The rows are ordered by `resume_id`, so all jobs for one resume stay together.

Do not change `pair_id`, `resume_id`, `job_id`, or `split`. Do not tune the system while annotation is in progress.

## Search the weights

The committed final labels are stored in
`annotation_pairs_ai_labeled_professional_v2.csv`. To run grouped five-fold
weight selection and compare the historical and final production weights:

```powershell
python scripts/cross_validate_ranking_weights.py --require-direct-gte-graph
```

The grid uses increments of 0.05, enforces non-negative weights summing to 1,
requires direct-skill weight to be at least graph weight, and maximizes mean
NDCG@10 on the training resumes in each fold. Direct and graph coverage are
mutually exclusive for each JD skill, and career intent is not part of this
search. Each selected configuration is evaluated only on the two held-out
resumes for that fold.

The committed result is `ranking_weight_cv_v4_constrained.json` and includes:

- historical, final, and fold-selected held-out NDCG@10;
- per-resume held-out scores;
- selected-weight frequency and paired comparison summaries.

Only adopt new production weights when test NDCG improves, hard-constraint violations remain zero, and the change is stable under a second split or cross-validation run.

The final v4 evaluation uses sentence-level resume evidence and grouped five-fold
cross-validation by resume. It selected `0.20 / 0.60 / 0.20` as the stable
production weights. Mean held-out NDCG@10 improved from `0.8214` for the
historical `0.30 / 0.45 / 0.25` model to `0.8453`.

## Run the ablation study

```powershell
python scripts/run_ranking_ablation.py
```

The ablation keeps the preferred-skill bonus, missing-component normalization,
dataset, folds, and ranking metric fixed. It removes one professional-fit module
at a time and proportionally renormalizes the remaining weights.

| Configuration | Weights (direct / responsibility / graph) | Mean NDCG@10 | Drop from full |
|---|---:|---:|---:|
| Full model | 0.20 / 0.60 / 0.20 | 0.8453 | - |
| Without direct skill | 0.00 / 0.75 / 0.25 | 0.8117 | 0.0337 |
| Without responsibility | 0.50 / 0.00 / 0.50 | 0.8044 | 0.0409 |
| Without knowledge graph | 0.25 / 0.75 / 0.00 | 0.8268 | 0.0185 |
| Direct skill only | 1.00 / 0.00 / 0.00 | 0.7554 | 0.0899 |
| Responsibility only | 0.00 / 1.00 / 0.00 | 0.8001 | 0.0453 |

The result is stored in `ranking_ablation_v4.json`. These are descriptive
results over ten resumes rather than a statistical significance claim.
