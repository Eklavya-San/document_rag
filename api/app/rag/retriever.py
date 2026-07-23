from dataclasses import dataclass
from app.config import Settings
from app.rag.embed_sparse import sparse_embed


@dataclass
class Source:
    text: str
    doc_id: int
    filename: str
    page: int
    score: float
    chunk_id: str


class Retriever:
    def __init__(self, embedder, qdrant, settings: Settings):
        self.embedder = embedder
        self.qdrant = qdrant
        self.settings = settings

    async def retrieve(self, question: str, query_filter=None) -> list[Source]:
        vectors = await self.embedder.embed([question])
        query_vector = vectors[0]
        if self.settings.hybrid_enabled:
            sparse_vecs = await self._sparse([question])
            kwargs = {"filter": query_filter} if query_filter is not None else {}
            hits = await self.qdrant.query_points(query_vector, sparse_vecs[0], self.settings.retrieval_top_k, **kwargs)
        else:
            kwargs = {"query_filter": query_filter} if query_filter is not None else {}
            hits = await self.qdrant.search(query_vector, self.settings.retrieval_top_k, **kwargs)

        if not hits:
            return []
        hits_sorted = sorted(hits, key=lambda h: h["score"], reverse=True)
        if hits_sorted[0]["score"] < self.settings.no_context_threshold:
            return []
        sources = [
            Source(
                text=h["text"],
                doc_id=h["doc_id"],
                filename=h["filename"],
                page=h["page"],
                score=h["score"],
                chunk_id=str(h.get("id", "")),
            )
            for h in hits_sorted
        ]
        if self.settings.rerank_enabled:
            sources = sources[: self.settings.rerank_top_k]
        return sources

    async def _sparse(self, texts: list[str]) -> list[dict]:
        if hasattr(self.embedder, "embed_sparse"):
            return await self.embedder.embed_sparse(texts)
        return sparse_embed(texts, self.settings.sparse_model)
