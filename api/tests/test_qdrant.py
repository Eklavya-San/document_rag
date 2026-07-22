from unittest.mock import MagicMock, patch
from app.config import Settings
from app.qdrant.client import QdrantStore


def test_ensure_collection_creates_with_configured_dim():
    settings = Settings(qdrant_url="http://qdrant:6333", embed_dim=768, ollama_embed_model="bge-m3")
    store = QdrantStore(settings)
    with patch.object(store, "_client") as mock_client:
        mock_client.collection_exists.return_value = False
        store.ensure_collection()
    mock_client.collection_exists.assert_called_once_with("manuals")
    mock_client.create_collection.assert_called_once()
    _, kwargs = mock_client.create_collection.call_args
    assert kwargs["vectors_config"].size == 768


def test_ensure_collection_skips_when_exists():
    settings = Settings(qdrant_url="http://qdrant:6333", embed_dim=1024)
    store = QdrantStore(settings)
    with patch.object(store, "_client") as mock_client:
        mock_client.collection_exists.return_value = True
        store.ensure_collection()
    mock_client.create_collection.assert_not_called()
