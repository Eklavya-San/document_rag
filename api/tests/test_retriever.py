from unittest.mock import AsyncMock
from app.config import Settings
from app.rag.retriever import Retriever, Source


async def test_retrieve_returns_sources_sorted():
    embedder = AsyncMock()
    embedder.embed = AsyncMock(return_value=[[0.1, 0.2]])
    qdrant = AsyncMock()
    qdrant.search = AsyncMock(return_value=[
        {"text": "b", "doc_id": 1, "filename": "m.pdf", "page": 2, "score": 0.8},
        {"text": "a", "doc_id": 1, "filename": "m.pdf", "page": 1, "score": 0.9},
    ])
    r = Retriever(embedder, qdrant, Settings(retrieval_top_k=5, no_context_threshold=0.35))
    sources = await r.retrieve("how to calibrate?")
    assert sources == [
        Source(text="a", doc_id=1, filename="m.pdf", page=1, score=0.9),
        Source(text="b", doc_id=1, filename="m.pdf", page=2, score=0.8),
    ]
    embedder.embed.assert_awaited_once_with(["how to calibrate?"])


async def test_retrieve_below_threshold_returns_empty():
    embedder = AsyncMock()
    embedder.embed = AsyncMock(return_value=[[0.1, 0.2]])
    qdrant = AsyncMock()
    qdrant.search = AsyncMock(return_value=[
        {"text": "x", "doc_id": 1, "filename": "m.pdf", "page": 1, "score": 0.2},
    ])
    r = Retriever(embedder, qdrant, Settings(no_context_threshold=0.35))
    assert await r.retrieve("anything") == []


async def test_retrieve_rerank_enabled_trims_to_four():
    embedder = AsyncMock()
    embedder.embed = AsyncMock(return_value=[[0.1]])
    hits = [{"text": str(i), "doc_id": 1, "filename": "m.pdf", "page": i, "score": 0.9 - i * 0.01} for i in range(6)]
    qdrant = AsyncMock()
    qdrant.search = AsyncMock(return_value=hits)
    r = Retriever(embedder, qdrant, Settings(retrieval_top_k=6, rerank_enabled=True, no_context_threshold=0.35))
    sources = await r.retrieve("q")
    assert len(sources) == 4


async def test_rerank_caps_to_rerank_top_k():
    from app.rag.retriever import Retriever
    from app.config import Settings
    class FakeEmb:
        async def embed(self, texts): return [[0.1] for _ in texts]
    class FakeQ:
        async def search(self, vector, top_k):
            return [{"text": f"t{i}", "doc_id": 1, "filename": "m.pdf", "page": i, "score": 0.9 - i*0.01} for i in range(top_k)]
    settings = Settings(retrieval_top_k=10, rerank_enabled=True, rerank_top_k=2)
    r = Retriever(FakeEmb(), FakeQ(), settings)
    sources = await r.retrieve("q")
    assert len(sources) == 2
