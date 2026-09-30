from __future__ import annotations

import argparse

from app.repositories.job_semantic_repository import JobSemanticRepository
from app.services.job_semantic_index_service import JobSemanticIndexService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill JD responsibility vectors and standard-role Top-K results."
    )
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args()
    if args.limit <= 0:
        parser.error("--limit must be greater than zero")

    repository = JobSemanticRepository()
    service = JobSemanticIndexService()
    documents = repository.list_analyzed_jobs(limit=args.limit)
    for index, document in enumerate(documents, start=1):
        service.index(document)
        print(f"[{index}/{len(documents)}] indexed job {document.job_id}")
    print(f"Indexed {len(documents)} analyzed jobs.")


if __name__ == "__main__":
    main()
