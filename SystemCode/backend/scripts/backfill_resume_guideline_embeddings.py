from __future__ import annotations

from app.core.config import settings
from app.matching.embedding_provider import SentenceTransformerEmbeddingProvider
from app.repositories.resume_guideline_repository import ResumeGuidelineRepository


def main() -> None:
    # 只处理没有向量（新增或内容改过后被清空）或换了模型的文本块，可以重复运行
    model_name = settings.resume_guideline_embedding_model
    repository = ResumeGuidelineRepository()
    pending = repository.list_chunks_needing_embeddings(model_name)
    if pending:
        provider = SentenceTransformerEmbeddingProvider(model_name)
        embeddings = provider.encode([chunk.chunk_text for chunk in pending])
        repository.save_chunk_embeddings(pending, embeddings, model_name)
    print(
        f"Embedded {len(pending)} of {repository.count_chunks()} chunks "
        f"({repository.count()} resume guidelines) with {model_name}."
    )


if __name__ == "__main__":
    main()
