from unittest.mock import AsyncMock, patch
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
