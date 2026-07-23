import asyncio
import uuid
from app.config import Settings
from app.db.repositories import DocumentRepository
from app.ollama.client import OllamaClient
from app.qdrant.client import QdrantStore
from app.ingestion.parsers import parse_file
import hashlib
from app.ingestion.chunker import chunk_pages

EMBED_BATCH = 32


_EMBED_CACHE: dict[str, list[float]] = {}


def _embed_key(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()


def _chunk_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()



def _detect_language(text: str) -> str:
    try:
        from langdetect import detect, DetectorFactory
        DetectorFactory.seed = 0
        return detect(text)
    except Exception:
        return "auto"




async def ingest_document(
    doc_id: int,
    file_path: str,
    filename: str,
    repo: DocumentRepository,
    embedder: OllamaClient,
    qdrant: QdrantStore,
    settings: Settings,
) -> None:
    try:
        await repo.set_status(doc_id, "parsing")
        pages = await asyncio.to_thread(parse_file, file_path, filename)
        parser_used = _parser_used(filename)
        if settings.token_accurate_chunking:
            chunks = chunk_pages(pages, settings.chunk_size_tokens, settings.chunk_overlap_tokens, token_accurate=True)
        else:
            size_chars = settings.chunk_size_tokens * 4
            overlap_chars = settings.chunk_overlap_tokens * 4
            chunks = chunk_pages(pages, size_chars, overlap_chars)

        if settings.dedup_enabled:
            seen = set()
            unique = []
            for c in chunks:
                h = _chunk_hash(c.text)
                if h in seen:
                    continue
                seen.add(h)
                unique.append(c)
            chunks = unique

        if not chunks:

            await repo.set_status(doc_id, "failed", parser_used=parser_used, error="No text extracted")
            return

        await repo.set_status(doc_id, "embedding", parser_used=parser_used, chunk_count=len(chunks))
        for i in range(0, len(chunks), EMBED_BATCH):
            batch = chunks[i:i + EMBED_BATCH]
            resolved: list[list[float] | None] = []
            to_embed = []
            for c in batch:
                k = _embed_key(c.text) if settings.embed_cache_enabled else None
                if k and k in _EMBED_CACHE:
                    resolved.append(_EMBED_CACHE[k])
                else:
                    resolved.append(None)
                    to_embed.append(c.text)
            new_vectors = await embedder.embed(to_embed) if to_embed else []
            ni = 0
            for idx, c in enumerate(batch):
                if resolved[idx] is None:
                    resolved[idx] = new_vectors[ni]
                    ni += 1
                    if settings.embed_cache_enabled:
                        _EMBED_CACHE[_embed_key(c.text)] = resolved[idx]
            vectors: list[list[float]] = [v for v in resolved if v is not None]
            sparse = await _sparse_batch(embedder, [c.text for c in batch], settings)

            points = [
                {
                    "id": str(uuid.uuid4()),
                    "vector": vector,
                    "sparse": sparse[j],
                    "payload": {
                        "doc_id": doc_id,
                        "filename": filename,
                        "page": chunk.page,
                        "section": getattr(chunk, "section", ""),
                        "text": chunk.text,
                        "language": _detect_language(chunk.text),


                    },
                }
                for j, (chunk, vector) in enumerate(zip(batch, vectors, strict=True))
            ]
            await qdrant.upsert(points=points)
        await repo.set_status(doc_id, "done", chunk_count=len(chunks), parser_used=parser_used)

    except Exception as e:
        try:
            await qdrant.delete_by_doc(doc_id)
        except Exception:
            pass  # best-effort cleanup; do not mask the original failure
        await repo.set_status(doc_id, "failed", error=str(e))


def _parser_used(filename: str) -> str:
    from pathlib import Path
    ext = Path(filename).suffix.lower().lstrip(".")
    return ext if ext in ("pdf", "docx", "html", "htm") else "unknown"


async def _sparse_batch(embedder, texts: list[str], settings: Settings) -> list:
    if not settings.hybrid_enabled:
        return [None] * len(texts)
    if hasattr(embedder, "embed_sparse"):
        return await embedder.embed_sparse(texts)
    from app.rag.embed_sparse import sparse_embed
    return await asyncio.to_thread(sparse_embed, texts, settings.sparse_model)

