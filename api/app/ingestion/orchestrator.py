import uuid
from app.config import Settings
from app.db.repositories import DocumentRepository
from app.ollama.client import OllamaClient
from app.qdrant.client import QdrantStore
from app.ingestion.parsers import parse_file
from app.ingestion.chunker import chunk_pages

EMBED_BATCH = 32


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
        pages = parse_file(file_path, filename)
        parser_used = _parser_used(filename)
        size_chars = settings.chunk_size_tokens * 4
        overlap_chars = settings.chunk_overlap_tokens * 4
        chunks = chunk_pages(pages, size_chars, overlap_chars)
        if not chunks:
            await repo.set_status(doc_id, "failed", parser_used=parser_used, error="No text extracted")
            return

        await repo.set_status(doc_id, "embedding", parser_used=parser_used, chunk_count=len(chunks))
        points = []
        for i in range(0, len(chunks), EMBED_BATCH):
            batch = chunks[i:i + EMBED_BATCH]
            vectors = await embedder.embed([c.text for c in batch])
            for chunk, vector in zip(batch, vectors, strict=True):
                points.append({
                    "id": str(uuid.uuid4()),
                    "vector": vector,
                    "payload": {
                        "doc_id": doc_id,
                        "filename": filename,
                        "page": chunk.page,
                        "text": chunk.text,
                        "language": "auto",
                    },
                })
        await qdrant.upsert(points=points)
        await repo.set_status(doc_id, "done", chunk_count=len(chunks), parser_used=parser_used)
    except Exception as e:
        await repo.set_status(doc_id, "failed", error=str(e))


def _parser_used(filename: str) -> str:
    from pathlib import Path
    ext = Path(filename).suffix.lower().lstrip(".")
    return ext if ext in ("pdf", "docx", "html", "htm") else "unknown"
