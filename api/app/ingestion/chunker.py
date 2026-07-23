from dataclasses import dataclass
from functools import lru_cache
from app.ingestion.parsers import Page


@dataclass
class Chunk:
    text: str
    page: int
    section: str = ""


@lru_cache(maxsize=1)
def _enc():
    import tiktoken
    return tiktoken.get_encoding("cl100k_base")


def _bound(text: str, start: int, budget: int, token_accurate: bool) -> int:
    if token_accurate:
        enc = _enc()
        tokens = enc.encode(text[start:])
        piece_ids = tokens[:budget]
        end = start + len(enc.decode(piece_ids))
        return min(end, len(text))
    return min(start + budget, len(text))


def chunk_pages(pages: list[Page], size_chars: int, overlap_chars: int, token_accurate: bool = False) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page in pages:
        text = page.text
        if not text.strip():
            continue
        start = 0
        n = len(text)
        while start < n:
            end = _bound(text, start, size_chars, token_accurate)
            if end < n:
                space = text.rfind(" ", start, end)
                if space > start:
                    end = space
            piece = text[start:end]
            if piece.strip():
                chunks.append(Chunk(text=piece, page=page.number, section=getattr(page, "section", "")))
            if end >= n:
                break
            next_start = end - overlap_chars
            start = next_start if next_start > start else start + 1
    return chunks
