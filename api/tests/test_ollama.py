import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from app.config import Settings
from app.ollama.client import OllamaClient


@pytest.mark.asyncio
async def test_ping_true_on_200():
    client = OllamaClient(Settings(ollama_base_url="http://gpu:11434"))
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch.object(client, "_http") as mock_http:
        mock_http.get = AsyncMock(return_value=mock_resp)
        assert await client.ping() is True


@pytest.mark.asyncio
async def test_ping_false_on_error():
    client = OllamaClient(Settings(ollama_base_url="http://gpu:11434"))
    with patch.object(client, "_http") as mock_http:
        mock_http.get = AsyncMock(side_effect=httpx.ConnectError("nope"))
        assert await client.ping() is False


@pytest.mark.asyncio
async def test_embed_returns_vectors():
    client = OllamaClient(Settings(ollama_base_url="http://gpu:11434", ollama_embed_model="bge-m3"))
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}
    mock_resp.raise_for_status = MagicMock()
    with patch.object(client, "_http") as mock_http:
        mock_http.post = AsyncMock(return_value=mock_resp)
        vecs = await client.embed(["hello", "world"])
    assert vecs == [[0.1, 0.2], [0.3, 0.4]]


@pytest.mark.asyncio
async def test_chat_stream_yields_content_pieces():
    client = OllamaClient(Settings(ollama_base_url="http://gpu:11434"))

    class FakeStream:
        def __init__(self):
            self._lines = iter(['{"message":{"content":"Hel"}}', '{"message":{"content":"lo"}}', ""])

        async def aiter_lines(self):
            for line in self._lines:
                yield line

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def raise_for_status(self):
            pass

    fake_stream = FakeStream()
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()

    with patch.object(client, "_http") as mock_http:
        mock_http.stream = MagicMock(return_value=fake_stream)
        pieces = []
        async for p in client.chat_stream([{"role": "user", "content": "hi"}]):
            pieces.append(p)
    assert pieces == ["Hel", "lo"]


@pytest.mark.asyncio
async def test_close_acloses_underlying_client():
    client = OllamaClient(Settings(ollama_base_url="http://gpu:11434"))
    with patch.object(client, "_http") as mock_http:
        mock_http.aclose = AsyncMock()
        await client.close()
    mock_http.aclose.assert_awaited_once()
