from app.config import Settings
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

COLLECTION = "manuals"


class QdrantStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = QdrantClient(url=settings.qdrant_url)

    def ensure_collection(self) -> None:
        if self._client.collection_exists(COLLECTION):
            return
        self._client.create_collection(
            collection_name=COLLECTION,
            vectors_config=qm.VectorParams(
                size=self.settings.embed_dim,
                distance=qm.Distance.COSINE,
            ),
        )
