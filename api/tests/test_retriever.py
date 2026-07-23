from unittest.mock import AsyncMock
from app.config import Settings
from app.rag.retriever import Retriever, Source


async def test_retrieve_returns_sources_sorted():
    embedder = AsyncMock()
    embedder.embed = AsyncMock(return_value=[[0.1, 0.2]])
    qdrant = AsyncMock()
    qdrant.search = AsyncMock(return_value=[
        {"id": "p2", "text": "b", "doc_id": 1, "filename": "m.pdf", "page": 2, "score": 0.8},
        {"id": "p1", "text": "a", "doc_id": 1, "filename": "m.pdf", "page": 1, "score": 0.9},
    ])
    r = Retriever(embedder, qdrant, Settings(retrieval_top_k=5, no_context_threshold=0.35))
    sources = await r.retrieve("how to calibrate?")
    assert sources == [
        Source(text="a", doc_id=1, filename="m.pdf", page=1, score=0.9, chunk_id="p1"),
        Source(text="b", doc_id=1, filename="m.pdf", page=2, score=0.8, chunk_id="p2"),
    ]
    embedder.embed.assert_awaited_once_with(["how to calibrate?"])


async def test_retrieve_below_threshold_returns_empty():
    embedder = AsyncMock()
    embedder.embed = AsyncMock(return_value=[[0.1, 0.2]])
    qdrant = AsyncMock()
    qdrant.search = AsyncMock(return_value=[
        {"id": "p0", "text": "x", "doc_id": 1, "filename": "m.pdf", "page": 1, "score": 0.2},
    ])
    r = Retriever(embedder, qdrant, Settings(no_context_threshold=0.35))
    assert await r.retrieve("anything") == []


async def test_retrieve_rerank_enabled_trims_to_four():
    embedder = AsyncMock()
    embedder.embed = AsyncMock(return_value=[[0.1]])
    hits = [{"id": f"p{i}", "text": str(i), "doc_id": 1, "filename": "m.pdf", "page": i, "score": 0.9 - i * 0.01} for i in range(6)]
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
            return [{"id": f"p{i}", "text": f"t{i}", "doc_id": 1, "filename": "m.pdf", "page": i, "score": 0.9 - i*0.01} for i in range(top_k)]
    settings = Settings(retrieval_top_k=10, rerank_enabled=True, rerank_top_k=2)
    r = Retriever(FakeEmb(), FakeQ(), settings)
    sources = await r.retrieve("q")
    assert len(sources) == 2


async def test_hybrid_search_issues_dense_and_sparse():
    from app.rag.retriever import Retriever
    from app.config import Settings
    calls = {}

    class FakeEmb:
        async def embed(self, texts): return [[0.1] for _ in texts]
        async def embed_sparse(self, texts):
            calls["sparse_text"] = texts
            return [{"indices": [0], "values": [1.0]} for _ in texts]

    class FakeQ:
        async def query_points(self, dense, sparse, top_k, filter=None):
            calls["dense"] = dense
            calls["sparse_vec"] = sparse
            return [{"id": "p1", "text": "t", "doc_id": 1, "filename": "m.pdf", "page": 1, "score": 0.9}]

        async def search(self, vector, top_k):
            raise AssertionError("dense-only search should not run when hybrid enabled")

    settings = Settings(hybrid_enabled=True, retrieval_top_k=5)
    r = Retriever(FakeEmb(), FakeQ(), settings)
    sources = await r.retrieve("how to calibrate")
    assert calls["dense"] == [0.1]
    assert calls["sparse_text"] == ["how to calibrate"]
    assert sources[0].chunk_id == "p1"


async def test_rerank_reorders_by_llm_score():
    from app.rag.retriever import Source
    from app.rag.rerank import rerank

    class JudgeOllama:
        async def chat(self, messages):
            return '{"scores": [0.1, 0.9]}'

    sources = [
        Source(text="a", doc_id=1, filename="m.pdf", page=1, score=0.95, chunk_id="a"),
        Source(text="b", doc_id=1, filename="m.pdf", page=2, score=0.80, chunk_id="b"),
    ]
    out = await rerank("how to calibrate", sources, JudgeOllama(), top_k=2)
    assert [s.chunk_id for s in out] == ["b", "a"]


async def test_multi_query_merges_dedup_by_chunk_id():
    from app.rag.retriever import Retriever
    from app.config import Settings

    class Judge:
        async def chat(self, messages):
            return '["how to calibrate", "calibration steps", "sensor calibration"]'

    class Emb:
        async def embed(self, texts): return [[0.1] for _ in texts]
        async def embed_sparse(self, texts): return [{"indices":[0],"values":[1.0]} for _ in texts]

    seen = []
    class Q:
        async def search(self, vector, top_k, query_filter=None):
            seen.append(vector)
            if len(seen) == 1:
                return [{"id":"a","text":"a","doc_id":1,"filename":"m.pdf","page":1,"score":0.9}]
            return [{"id":"a","text":"a","doc_id":1,"filename":"m.pdf","page":1,"score":0.9},
                    {"id":"b","text":"b","doc_id":1,"filename":"m.pdf","page":2,"score":0.85}]

    settings = Settings(query_expansion_enabled=True, num_subqueries=3, retrieval_top_k=5)
    r = Retriever(Emb(), Q(), settings, judge=Judge())
    sources = await r.retrieve("how to calibrate")
    ids = {s.chunk_id for s in sources}
    assert ids == {"a", "b"}
    assert len(seen) == 3


async def test_context_dedup_drops_duplicate_text():
    from app.rag.retriever import Retriever
    from app.config import Settings

    class Emb:
        async def embed(self, texts): return [[0.1]]
    class Q:
        async def search(self, vector, top_k, query_filter=None):
            return [
                {"id":"a","text":"calibrate the sensor","doc_id":1,"filename":"m.pdf","page":1,"score":0.9},
                {"id":"b","text":"calibrate the sensor","doc_id":1,"filename":"m.pdf","page":2,"score":0.85},
            ]
    settings = Settings(context_dedup_enabled=True, retrieval_top_k=5)
    r = Retriever(Emb(), Q(), settings)
    sources = await r.retrieve("q")
    assert len(sources) == 1


async def test_query_embed_cache_hits_once_for_same_question():
    from app.rag.retriever import Retriever
    from app.config import Settings
    count = {"n": 0}
    class Emb:
        async def embed(self, texts):
            count["n"] += 1
            return [[0.1] for _ in texts]
    class Q:
        async def search(self, vector, top_k, query_filter=None):
            return [{"id":"a","text":"t","doc_id":1,"filename":"m.pdf","page":1,"score":0.9}]
    settings = Settings(embed_cache_enabled=True, retrieval_top_k=5)
    r = Retriever(Emb(), Q(), settings)
    await r.retrieve("same question")
    await r.retrieve("same question")
    assert count["n"] == 1


async def test_empty_hits_returns_empty():
    from app.rag.retriever import Retriever
    from app.config import Settings
    class Emb:
        async def embed(self, texts): return [[0.1]]
    class Q:
        async def search(self, vector, top_k, query_filter=None): return []
    r = Retriever(Emb(), Q(), Settings(no_context_threshold=0.35, retrieval_top_k=5))
    assert await r.retrieve("q") == []


async def test_score_equal_to_threshold_returns_sources():
    from app.rag.retriever import Retriever
    from app.config import Settings
    class Emb:
        async def embed(self, texts): return [[0.1]]
    class Q:
        async def search(self, vector, top_k, query_filter=None):
            return [{"id":"a","text":"t","doc_id":1,"filename":"m.pdf","page":1,"score":0.35}]
    r = Retriever(Emb(), Q(), Settings(no_context_threshold=0.35, retrieval_top_k=5))
    sources = await r.retrieve("q")
    assert len(sources) == 1







