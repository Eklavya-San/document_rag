from dataclasses import dataclass
from app.ingestion.parsers import Page


@dataclass
class Chunk:
    text: str
    page: int


def chunk_pages(pages: list[Page], size_chars: int, overlap_chars: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page in pages:
        text = page.text
        if not text.strip():
            continue
        start = 0
        n = len(text)
        while start < n:
            end = min(start + size_chars, n)
            if end < n:
                space = text.rfind(" ", start, end)
                if space > start:
                    end = space
            piece = text[start:end]
            if piece.strip():
                chunks.append(Chunk(text=piece, page=page.number))
            if end >= n:
                break
            next_start = end - overlap_chars
            start = next_start if next_start > start else start + 1
    return chunks
