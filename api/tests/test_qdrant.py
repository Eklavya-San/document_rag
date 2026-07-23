from unittest.mock import AsyncMock, MagicMock, patch
from app.config import Settings
from app.qdrant.client import QdrantStore


def _store(dim=1024):
    return QdrantStore(Settings(qdrant_url="http://qdrant:6333", embed_dim=dim))


async def test_ensure_collection_creates_with_configured_dim():
    store = _store(768)
    with patch.object(store, "_client") as mock_client:
        mock_client.collection_exists = AsyncMock(return_value=False)
        mock_client.create_collection = AsyncMock()
        await store.ensure_collection()
    mock_client.collection_exists.assert_awaited_once_with("manuals")
    mock_client.create_collection.assert_awaited_once()
    _, kwargs = mock_client.create_collection.call_args
    assert kwargs["vectors_config"].size == 768


async def test_ensure_collection_skips_when_exists():
    store = _store(1024)
    with patch.object(store, "_client") as mock_client:
        mock_client.collection_exists = AsyncMock(return_value=True)
        mock_client.create_collection = AsyncMock()
        await store.ensure_collection()
    mock_client.create_collection.assert_not_awaited()


async def test_upsert_sends_points():
    store = _store()
    with patch.object(store, "_client") as mock_client:
        mock_client.upsert = AsyncMock()
        await store.upsert([
            {"id": "u1", "vector": [0.1, 0.2], "payload": {"doc_id": 1, "page": 1, "text": "hi"}}
        ])
    mock_client.upsert.assert_awaited_once()
    _, kwargs = mock_client.upsert.call_args
    points = kwargs["points"]
    assert points[0].id == "u1"
    assert points[0].payload["doc_id"] == 1


async def test_delete_by_doc_uses_filter():
    store = _store()
    with patch.object(store, "_client") as mock_client:
        mock_client.delete = AsyncMock()
        await store.delete_by_doc(7)
    mock_client.delete.assert_awaited_once()
    _, kwargs = mock_client.delete.call_args
    sel = kwargs["points_selector"]
    assert sel.must[0].key == "doc_id"
    assert sel.must[0].match.value == 7


async def test_search_maps_hits_to_dicts():
    store = _store()
    fake_hit = MagicMock()
    fake_hit.id = "p1"
    fake_hit.score = 0.91
    fake_hit.payload = {"text": "calibrate", "doc_id": 1, "filename": "m.pdf", "page": 3}
    with patch.object(store, "_client") as mock_client:
        mock_client.search = AsyncMock(return_value=[fake_hit])
        results = await store.search([0.1, 0.2], top_k=5)
    mock_client.search.assert_awaited_once()
    _, kwargs = mock_client.search.call_args
    assert kwargs["collection_name"] == "manuals"
    assert kwargs["limit"] == 5
    assert results == [{"id": "p1", "text": "calibrate", "doc_id": 1, "filename": "m.pdf", "page": 3, "section": "", "score": 0.91}]



async def test_search_returns_point_id():
    store = _store()
    class Scored:
        id = "point-42"
        score = 0.9
        payload = {"text": "t", "doc_id": 1, "filename": "m.pdf", "page": 2}
    class FakeClient:
        async def search(self, **kwargs): return [Scored()]
        async def close(self): pass
    store._client = FakeClient()
    hits = await store.search([0.1], 5)
    assert hits[0]["id"] == "point-42"
    assert hits[0]["text"] == "t"


async def test_close_closes_underlying_client():
    store = _store()
    with patch.object(store, "_client") as mock_client:
        mock_client.close = AsyncMock()
        await store.close()
    mock_client.close.assert_awaited_once()
