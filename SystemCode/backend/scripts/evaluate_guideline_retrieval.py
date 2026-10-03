"""评测简历改写知识库的检索效果：hit@k 和 MRR，对比"只检索说明块"和"说明块 + 示例块"。

用法：python -m scripts.evaluate_guideline_retrieval
评测用例在同目录 guideline_retrieval_cases.json，query 是手写的弱要点，刻意不与知识库示例原句重复；
expected 里任意一个 key 出现在结果中即算命中。
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.matching.embedding_provider import SentenceTransformerEmbeddingProvider
from app.repositories.resume_guideline_repository import ResumeGuidelineRepository

CASES_PATH = Path(__file__).with_name("guideline_retrieval_cases.json")
TOP_K = 3
# 计算 MRR 时看得更深一些，避免命中在第 4 名以后时直接记 0
MRR_DEPTH = 10
MODES = {
    "guideline chunks only": ("guideline",),
    "guideline + example chunks": ("guideline", "example"),
}


def main() -> None:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    model_name = settings.resume_guideline_embedding_model
    provider = SentenceTransformerEmbeddingProvider(model_name)
    repository = ResumeGuidelineRepository()
    queries = provider.encode([case["query"] for case in cases])

    print(f"{len(cases)} cases, model={model_name}")
    for label, chunk_types in MODES.items():
        hits, reciprocal_ranks, misses = 0, 0.0, []
        for case, query in zip(cases, queries, strict=True):
            matches = repository.search(
                query,
                model_name=model_name,
                sections=case["sections"],
                issue_types=case["issue_types"],
                role_categories=[case["role_category"]] if case["role_category"] else [],
                top_k=MRR_DEPTH,
                chunk_types=chunk_types,
            )
            keys = [match.guideline.key for match in matches]
            rank = next((i + 1 for i, key in enumerate(keys) if key in case["expected"]), None)
            if rank is not None and rank <= TOP_K:
                hits += 1
            else:
                misses.append((case["query"], keys[:TOP_K]))
            reciprocal_ranks += 1 / rank if rank else 0.0
        print(f"\n[{label}] hit@{TOP_K} = {hits / len(cases):.3f}  MRR@{MRR_DEPTH} = {reciprocal_ranks / len(cases):.3f}")
        for query, keys in misses:
            print(f"  miss: {query[:70]!r} -> {keys}")


if __name__ == "__main__":
    main()
