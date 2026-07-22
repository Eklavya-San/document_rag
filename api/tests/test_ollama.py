import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from app.config import Settings
from app.ollama.client import OllamaClient


@pytest.mark.asyncio
async def test_ping_true_on_200():
    client = OllamaClient(Settings(ollama_base_url="http://gpu:11434"))
    with patch("app.ollama.client.httpx.AsyncClient") as MockClient:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        instance = MockClient.return_value
        instance.__aenter__.return_value = instance
        instance.get = AsyncMock(return_value=mock_resp)
        assert await client.ping() is True


@pytest.mark.asyncio
async def test_ping_false_on_error():
    client = OllamaClient(Settings(ollama_base_url="http://gpu:11434"))
    with patch("app.ollama.client.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value
        instance.__aenter__.return_value = instance
        instance.get = AsyncMock(side_effect=httpx.ConnectError("nope"))
        assert await client.ping() is False
