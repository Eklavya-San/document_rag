from dataclasses import dataclass
from app.config import Settings


@dataclass
class Source:
    text: str
    doc_id: int
    filename: str
    page: int
    score: float


class Retriever:
    def __init__(self, embedder, qdrant, settings: Settings):
        self.embedder = embedder
        self.qdrant = qdrant
        self.settings = settings

    async def retrieve(self, question: str) -> list[Source]:
        vectors = await self.embedder.embed([question])
        query_vector = vectors[0]
        hits = await self.qdrant.search(query_vector, self.settings.retrieval_top_k)
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
            )
            for h in hits_sorted
        ]
        if self.settings.rerank_enabled:
            sources = sources[: self.settings.rerank_top_k]
        return sources
