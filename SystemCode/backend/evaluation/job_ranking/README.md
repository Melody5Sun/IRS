# Job ranking weight evaluation

This evaluation tunes the three professional-fit ranking weights against relevance labels.
It does not modify production weights automatically.

## Dataset

- Ten anonymized resumes are configured in `profiles.json`.
- Each resume contributes 20 jobs that already passed production hard constraints.
- Sampling is stratified across four baseline-score quartiles so the annotation set contains strong, borderline, and weak matches.
- The first seven resumes form the validation split. The final three resumes form the held-out test split. Splitting by resume prevents the same candidate from appearing in both sets.
- `annotation_pairs_three_level_professional_v2.csv` is the final three-level annotation file. It contains 200 reviewed labels and is grouped by resume.
- `pair_features_resume_segments_v5.jsonl` contains the matching component coverages used by the optimizer. Every included JD has at least one responsibility; jobs with insufficient JD data are excluded before sampling.

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
`annotation_pairs_three_level_professional_v2.csv`. To run grouped five-fold
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

The committed result is `ranking_weight_cv_v5_constrained.json` and includes:

- historical, final, and fold-selected held-out NDCG@10;
- per-resume held-out scores;
- selected-weight frequency and paired comparison summaries.

Only adopt new production weights when test NDCG improves, hard-constraint violations remain zero, and the change is stable under a second split or cross-validation run.

The final v5 evaluation uses sentence-level resume evidence, excludes JDs without
responsibility data, and applies grouped five-fold cross-validation by resume.
The production `0.20 / 0.60 / 0.20` weights remain the stable choice. Mean
held-out NDCG@10 improves from `0.8296` for the historical
`0.30 / 0.45 / 0.25` model to `0.8412`.

## Run the ablation study

```powershell
python scripts/run_ranking_ablation.py
```

The ablation keeps the preferred-skill bonus, missing-component normalization,
dataset, folds, and ranking metric fixed. It removes one professional-fit module
at a time and proportionally renormalizes the remaining weights.

| Configuration | Weights (direct / responsibility / graph) | Mean NDCG@10 | Drop from full |
|---|---:|---:|---:|
| Full model | 0.20 / 0.60 / 0.20 | 0.8412 | - |
| Without direct skill | 0.00 / 0.75 / 0.25 | 0.8123 | 0.0289 |
| Without responsibility | 0.50 / 0.00 / 0.50 | 0.8171 | 0.0241 |
| Without knowledge graph | 0.25 / 0.75 / 0.00 | 0.8382 | 0.0030 |
| Direct skill only | 1.00 / 0.00 / 0.00 | 0.7738 | 0.0674 |
| Responsibility only | 0.00 / 1.00 / 0.00 | 0.7844 | 0.0568 |

The result is stored in `ranking_ablation_v5.json`. These are descriptive
results over ten resumes rather than a statistical significance claim.

## Three-level recommendation thresholds

The current `4 / 16` thresholds achieve held-out test accuracy `0.5667` and
Macro-F1 `0.5198`. Searching the validation split selects `8 / 15`, but that
choice falls to accuracy `0.4500` and Macro-F1 `0.4692` on the test split.
Therefore production retains `4 / 16` rather than adopting the validation-only
optimum.
