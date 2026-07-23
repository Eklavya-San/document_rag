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
        if self.settings.hybrid_enabled:
            vectors_config = {"dense": qm.VectorParams(size=self.settings.embed_dim, distance=qm.Distance.COSINE)}
            sparse_vectors_config = {"sparse": qm.SparseVectorParams()}
        else:
            vectors_config = qm.VectorParams(size=self.settings.embed_dim, distance=qm.Distance.COSINE)
            sparse_vectors_config = None

        kwargs = {"collection_name": COLLECTION, "vectors_config": vectors_config}
        if sparse_vectors_config is not None:
            kwargs["sparse_vectors_config"] = sparse_vectors_config

        await self._client.create_collection(**kwargs)


    async def upsert(self, points: list[dict]) -> None:
        mapped = []
        for p in points:
            if self.settings.hybrid_enabled:
                vectors = {"dense": p["vector"]}
                if p.get("sparse") is not None:
                    vectors["sparse"] = qm.SparseVector(indices=p["sparse"]["indices"], values=p["sparse"]["values"])
            else:
                vectors = p["vector"]
            mapped.append(PointStruct(id=p["id"], vector=vectors, payload=p["payload"]))
        await self._client.upsert(collection_name=COLLECTION, points=mapped)

    async def delete_by_doc(self, doc_id: int) -> None:
        await self._client.delete(
            collection_name=COLLECTION,
            points_selector=qm.Filter(
                must=[qm.FieldCondition(key="doc_id", match=qm.MatchValue(value=doc_id))]
            ),
        )

    async def search(self, query_vector: list[float], top_k: int, query_filter=None) -> list[dict]:
        qv = ("dense", query_vector) if self.settings.hybrid_enabled else query_vector
        results = await self._client.search(
            collection_name=COLLECTION,
            query_vector=qv,
            limit=top_k,
            query_filter=query_filter,
        )
        return [
            {
                "id": r.id,
                "text": r.payload.get("text", ""),
                "doc_id": r.payload.get("doc_id"),
                "filename": r.payload.get("filename", ""),
                "page": r.payload.get("page"),
                "section": r.payload.get("section", ""),
                "score": r.score,
            }
            for r in results
        ]

    async def query_points(self, dense, sparse, top_k, filter=None) -> list[dict]:
        prefetch = [
            qm.Prefetch(query=dense, using="dense", limit=top_k * 4),
            qm.Prefetch(query=qm.SparseVector(indices=sparse["indices"], values=sparse["values"]), using="sparse", limit=top_k * 4),
        ]
        res = await self._client.query_points(
            collection_name=COLLECTION,
            prefetch=prefetch,
            query=qm.FusionQuery(fusion=qm.Fusion.RRF),
            limit=top_k,
            query_filter=filter,
        )
        points = res.points if hasattr(res, "points") else res
        return [
            {
                "id": p.id,
                "text": p.payload.get("text", ""),
                "doc_id": p.payload.get("doc_id"),
                "filename": p.payload.get("filename", ""),
                "page": p.payload.get("page"),
                "section": p.payload.get("section", ""),
                "score": p.score,
            }
            for p in points
        ]


    async def ping(self) -> bool:
        try:
            await self._client.get_collection(COLLECTION)
            return True
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.close()
