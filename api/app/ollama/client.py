from collections.abc import AsyncIterator
import httpx


class OllamaClient:
    def __init__(self, settings):
        self.settings = settings
        self._base = settings.ollama_base_url.rstrip("/")

    async def ping(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as c:
                r = await c.get(f"{self._base}/api/tags")
                return r.status_code == 200
        except httpx.HTTPError:
            return False

    async def embed(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=60.0) as c:
            r = await c.post(
                f"{self._base}/api/embed",
                json={"model": self.settings.ollama_embed_model, "input": texts},
            )
            r.raise_for_status()
            return r.json()["embeddings"]

    async def chat_stream(
        self, messages: list[dict], model: str | None = None
    ) -> AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=None) as c:
            async with c.stream(
                "POST",
                f"{self._base}/api/chat",
                json={"model": model or self.settings.ollama_llm_model,
                      "messages": messages, "stream": True},
            ) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    import json
                    chunk = json.loads(line)
                    piece = chunk.get("message", {}).get("content", "")
                    if piece:
                        yield piece
