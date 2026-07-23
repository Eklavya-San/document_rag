import json
from collections.abc import AsyncIterator
import httpx
from app.config import Settings


class OllamaClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._base = settings.ollama_base_url.rstrip("/")
        self._http = httpx.AsyncClient(timeout=None)

    async def close(self) -> None:
        await self._http.aclose()

    async def ping(self) -> bool:
        try:
            r = await self._http.get(f"{self._base}/api/tags", timeout=3.0)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    async def embed(self, texts: list[str]) -> list[list[float]]:
        r = await self._http.post(
            f"{self._base}/api/embed",
            json={"model": self.settings.ollama_embed_model, "input": texts},
            timeout=60.0,
        )
        r.raise_for_status()
        return r.json()["embeddings"]

    async def chat_stream(
        self, messages: list[dict], model: str | None = None
    ) -> AsyncIterator[str]:
        async with self._http.stream(
            "POST",
            f"{self._base}/api/chat",
            json={"model": model or self.settings.ollama_llm_model,
                  "messages": messages, "stream": True},
            timeout=httpx.Timeout(10.0, read=120.0),
        ) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                piece = chunk.get("message", {}).get("content", "")
                if piece:
                    yield piece

    async def chat(self, messages: list[dict], model: str | None = None) -> str:
        r = await self._http.post(
            f"{self._base}/api/chat",
            json={"model": model or self.settings.ollama_llm_model, "messages": messages, "stream": False},
            timeout=60.0,
        )
        r.raise_for_status()
        return r.json()["message"]["content"]

