from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import text

from app.db.postgres import get_postgres_engine
from app.knowledge.guideline_source_registry import GuidelineSource
from app.repositories.job_semantic_repository import JobSemanticRepository
from app.schemas.resume_guideline import IssueType, ResumeGuideline, ResumeSection


ChunkType = Literal["guideline", "example"]


@dataclass(frozen=True)
class GuidelineChunk:
    id: int
    chunk_text: str


@dataclass(frozen=True)
class GuidelineMatch:
    guideline: ResumeGuideline
    similarity: float
    # 命中的文本块（说明块或某个示例的改写前原句），用来解释"为什么检索到这条"
    matched_chunk_type: ChunkType
    matched_chunk_text: str


class ResumeGuidelineRepository:
    """简历改写专家知识库。

    知识层：guideline_sources / resume_guidelines / resume_guideline_role_categories / resume_guideline_examples；
    向量层：resume_guideline_chunks（每条一个说明块 + 每个示例一个示例块）。
    """

    def upsert_sources(self, sources: list[GuidelineSource]) -> None:
        with get_postgres_engine().begin() as connection:
            for source in sources:
                connection.execute(
                    text(
                        """
                        INSERT INTO guideline_sources (name, provider, identifier, url, license, retrieved_at)
                        VALUES (:name, :provider, :identifier, :url, :license, :retrieved_at)
                        ON CONFLICT (name) DO UPDATE SET
                            provider = EXCLUDED.provider,
                            identifier = EXCLUDED.identifier,
                            url = EXCLUDED.url,
                            license = EXCLUDED.license,
                            retrieved_at = EXCLUDED.retrieved_at
                        """
                    ),
                    source.__dict__,
                )

    def upsert_many(self, guidelines: list[ResumeGuideline]) -> int:
        with get_postgres_engine().begin() as connection:
            for guideline in guidelines:
                self._upsert_one(connection, guideline)
        return len(guidelines)

    def _upsert_one(self, connection, guideline: ResumeGuideline) -> None:
        payload = guideline.model_dump(exclude={"id"})
        guideline_id = connection.execute(
            text(
                """
                INSERT INTO resume_guidelines (
                    guideline_key, source_id, source_url, title, guideline, rationale,
                    sections, issue_types, content_hash
                ) VALUES (
                    :key, (SELECT id FROM guideline_sources WHERE name = :source), :source_url,
                    :title, :guideline, :rationale, :sections, :issue_types, :content_hash
                )
                ON CONFLICT (guideline_key) DO UPDATE SET
                    source_id = EXCLUDED.source_id,
                    source_url = EXCLUDED.source_url,
                    title = EXCLUDED.title,
                    guideline = EXCLUDED.guideline,
                    rationale = EXCLUDED.rationale,
                    sections = EXCLUDED.sections,
                    issue_types = EXCLUDED.issue_types,
                    status = 'active',
                    updated_at = CASE
                        WHEN resume_guidelines.content_hash = EXCLUDED.content_hash
                        THEN resume_guidelines.updated_at ELSE CURRENT_TIMESTAMP END,
                    content_hash = EXCLUDED.content_hash
                RETURNING id
                """
            ),
            {**payload, "content_hash": self._content_hash(payload)},
        ).scalar_one()

        connection.execute(
            text("DELETE FROM resume_guideline_role_categories WHERE guideline_id = :id"),
            {"id": guideline_id},
        )
        for category in guideline.role_categories:
            connection.execute(
                text(
                    """
                    INSERT INTO resume_guideline_role_categories (guideline_id, role_category)
                    VALUES (:id, :category)
                    """
                ),
                {"id": guideline_id, "category": category},
            )

        # 示例按序号覆盖，多出来的旧示例连同它的文本块一起删除（外键级联）
        example_ids: list[int] = []
        for sequence_no, example in enumerate(guideline.examples):
            example_ids.append(
                connection.execute(
                    text(
                        """
                        INSERT INTO resume_guideline_examples (guideline_id, sequence_no, before_text, after_text)
                        VALUES (:id, :sequence_no, :before, :after)
                        ON CONFLICT (guideline_id, sequence_no) DO UPDATE SET
                            before_text = EXCLUDED.before_text,
                            after_text = EXCLUDED.after_text
                        RETURNING id
                        """
                    ),
                    {"id": guideline_id, "sequence_no": sequence_no, "before": example.before, "after": example.after},
                ).scalar_one()
            )
        connection.execute(
            text("DELETE FROM resume_guideline_examples WHERE guideline_id = :id AND sequence_no >= :count"),
            {"id": guideline_id, "count": len(guideline.examples)},
        )

        # 文本块内容没变就保留原向量，变了就清空等待回填
        for example_index, chunk_text in guideline.chunk_texts():
            connection.execute(
                text(
                    """
                    INSERT INTO resume_guideline_chunks (
                        guideline_id, example_id, chunk_type, chunk_text, content_hash
                    ) VALUES (:id, :example_id, :chunk_type, :chunk_text, :content_hash)
                    ON CONFLICT (guideline_id, example_id) DO UPDATE SET
                        chunk_text = EXCLUDED.chunk_text,
                        embedding = CASE WHEN resume_guideline_chunks.content_hash = EXCLUDED.content_hash
                            THEN resume_guideline_chunks.embedding END,
                        embedding_model = CASE WHEN resume_guideline_chunks.content_hash = EXCLUDED.content_hash
                            THEN resume_guideline_chunks.embedding_model END,
                        embedded_at = CASE WHEN resume_guideline_chunks.content_hash = EXCLUDED.content_hash
                            THEN resume_guideline_chunks.embedded_at END,
                        content_hash = EXCLUDED.content_hash
                    """
                ),
                {
                    "id": guideline_id,
                    "example_id": None if example_index is None else example_ids[example_index],
                    "chunk_type": "guideline" if example_index is None else "example",
                    "chunk_text": chunk_text,
                    "content_hash": JobSemanticRepository.content_hash(chunk_text),
                },
            )

    def count(self) -> int:
        with get_postgres_engine().connect() as connection:
            return connection.execute(text("SELECT COUNT(*) FROM resume_guidelines")).scalar_one()

    def count_chunks(self) -> int:
        with get_postgres_engine().connect() as connection:
            return connection.execute(text("SELECT COUNT(*) FROM resume_guideline_chunks")).scalar_one()

    def list_chunks_needing_embeddings(self, model_name: str) -> list[GuidelineChunk]:
        with get_postgres_engine().connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT id, chunk_text
                    FROM resume_guideline_chunks
                    WHERE embedding IS NULL OR embedding_model IS DISTINCT FROM :model_name
                    ORDER BY id
                    """
                ),
                {"model_name": model_name},
            ).all()
        return [GuidelineChunk(row.id, row.chunk_text) for row in rows]

    def save_chunk_embeddings(
        self,
        chunks: list[GuidelineChunk],
        embeddings: list[list[float]],
        model_name: str,
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have equal length")
        with get_postgres_engine().begin() as connection:
            for chunk, vector in zip(chunks, embeddings, strict=True):
                connection.execute(
                    text(
                        """
                        UPDATE resume_guideline_chunks
                        SET embedding = CAST(:embedding AS vector),
                            embedding_model = :model_name,
                            embedded_at = CURRENT_TIMESTAMP
                        WHERE id = :id
                        """
                    ),
                    {"embedding": JobSemanticRepository._vector_literal(vector), "model_name": model_name, "id": chunk.id},
                )

    def search(
        self,
        query_embedding: list[float],
        *,
        model_name: str,
        sections: list[ResumeSection],
        issue_types: list[IssueType],
        role_category: str | None = None,
        top_k: int = 3,
        chunk_types: tuple[ChunkType, ...] = ("guideline", "example"),
    ) -> list[GuidelineMatch]:
        """先按段落、问题类型（任一重叠即可）、岗位大类过滤条目，再在文本块上做余弦检索，
        每条条目取最相近的一个块，按相似度返回 top_k 条。role_category 为 None 时不按大类过滤。"""
        with get_postgres_engine().connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT guideline_id, chunk_type, chunk_text, distance
                    FROM (
                        SELECT DISTINCT ON (c.guideline_id)
                               c.guideline_id, c.chunk_type, c.chunk_text,
                               c.embedding <=> CAST(:query AS vector) AS distance
                        FROM resume_guideline_chunks c
                        JOIN resume_guidelines g ON g.id = c.guideline_id
                        WHERE c.embedding IS NOT NULL
                          AND c.embedding_model = :model_name
                          AND c.chunk_type = ANY(CAST(:chunk_types AS TEXT[]))
                          AND g.status = 'active'
                          AND g.sections && CAST(:sections AS TEXT[])
                          AND g.issue_types && CAST(:issue_types AS TEXT[])
                          AND (
                              CAST(:role_category AS TEXT) IS NULL
                              OR NOT EXISTS (
                                  SELECT 1 FROM resume_guideline_role_categories rc
                                  WHERE rc.guideline_id = g.id
                              )
                              OR EXISTS (
                                  SELECT 1 FROM resume_guideline_role_categories rc
                                  WHERE rc.guideline_id = g.id AND rc.role_category = CAST(:role_category AS TEXT)
                              )
                          )
                        ORDER BY c.guideline_id, distance
                    ) best
                    ORDER BY distance
                    LIMIT :top_k
                    """
                ),
                {
                    "query": JobSemanticRepository._vector_literal(query_embedding),
                    "model_name": model_name,
                    "chunk_types": list(chunk_types),
                    "sections": list(sections),
                    "issue_types": list(issue_types),
                    "role_category": role_category,
                    "top_k": top_k,
                },
            ).all()
            guidelines = self._load(connection, [row.guideline_id for row in rows])
        return [
            GuidelineMatch(
                guideline=guidelines[row.guideline_id],
                similarity=1 - float(row.distance),
                matched_chunk_type=row.chunk_type,
                matched_chunk_text=row.chunk_text,
            )
            for row in rows
        ]

    @staticmethod
    def _load(connection, ids: list[int]) -> dict[int, ResumeGuideline]:
        if not ids:
            return {}
        rows = connection.execute(
            text(
                """
                SELECT g.id, g.guideline_key, s.name AS source, g.source_url, g.title, g.guideline,
                       g.rationale, g.sections, g.issue_types,
                       COALESCE((
                           SELECT json_agg(json_build_object('before', e.before_text, 'after', e.after_text)
                                           ORDER BY e.sequence_no)
                           FROM resume_guideline_examples e WHERE e.guideline_id = g.id
                       ), '[]') AS examples,
                       ARRAY(
                           SELECT rc.role_category FROM resume_guideline_role_categories rc
                           WHERE rc.guideline_id = g.id ORDER BY rc.role_category
                       ) AS role_categories
                FROM resume_guidelines g
                JOIN guideline_sources s ON s.id = g.source_id
                WHERE g.id = ANY(CAST(:ids AS BIGINT[]))
                """
            ),
            {"ids": ids},
        ).mappings().all()
        return {
            row["id"]: ResumeGuideline(
                id=row["id"],
                key=row["guideline_key"],
                source=row["source"],
                source_url=row["source_url"],
                title=row["title"],
                guideline=row["guideline"],
                rationale=row["rationale"],
                examples=row["examples"],
                sections=list(row["sections"]),
                issue_types=list(row["issue_types"]),
                role_categories=list(row["role_categories"]),
            )
            for row in rows
        }

    @staticmethod
    def _content_hash(payload: dict) -> str:
        return JobSemanticRepository.content_hash(json.dumps(payload, sort_keys=True, ensure_ascii=False))
