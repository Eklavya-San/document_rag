from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qm
from qdrant_client.models import PointStruct
from app.config import Settings

COLLECTION = "manuals"


class QdrantStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = AsyncQdrantClient(url=settings.qdrant_url)

    async def ensure_collection(self) -> None:
        if await self._client.collection_exists(COLLECTION):
            return
        await self._client.create_collection(
            collection_name=COLLECTION,
            vectors_config=qm.VectorParams(
                size=self.settings.embed_dim,
                distance=qm.Distance.COSINE,
            ),
        )

    async def upsert(self, points: list[dict]) -> None:
        mapped = [
            PointStruct(id=p["id"], vector=p["vector"], payload=p["payload"])
            for p in points
        ]
        await self._client.upsert(collection_name=COLLECTION, points=mapped)

    async def delete_by_doc(self, doc_id: int) -> None:
        await self._client.delete(
            collection_name=COLLECTION,
            points_selector=qm.Filter(
                must=[qm.FieldCondition(key="doc_id", match=qm.MatchValue(value=doc_id))]
            ),
        )
