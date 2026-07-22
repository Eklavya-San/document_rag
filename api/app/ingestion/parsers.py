from dataclasses import dataclass
from pathlib import Path
from bs4 import BeautifulSoup
from pypdf import PdfReader


@dataclass
class Page:
    number: int
    text: str


class OcrRequiredError(Exception):
    pass


class UnsupportedFileError(Exception):
    pass


def parse_file(path: str, filename: str) -> list[Page]:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return _parse_pdf(path)
    if ext == ".docx":
        return _parse_docx(path)
    if ext in (".html", ".htm"):
        return _parse_html(path)
    raise UnsupportedFileError(f"Unsupported file type: {ext}")


def _parse_pdf(path: str) -> list[Page]:
    reader = PdfReader(path)
    pages: list[Page] = []
    for i, raw in enumerate(reader.pages, start=1):
        text = (raw.extract_text() or "").strip()
        if not text:
            raise OcrRequiredError(
                "PDF page has no extractable text (scanned?). OCR not yet supported (planned)."
            )
        pages.append(Page(number=i, text=text))
    return pages


def _parse_docx(path: str) -> list[Page]:
    import zipfile
    from app.config import get_settings
    limit = get_settings().docx_max_decompressed_bytes
    total = 0
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            total += info.file_size
            if total > limit:
                raise UnsupportedFileError("DOCX decompressed size exceeds limit (possible zip bomb)")
        from docx import Document as DocxDocument
        # python-docx re-opens the file; safe now that we validated sizes
        doc = DocxDocument(path)
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [Page(number=1, text=text)]


def _parse_html(path: str) -> list[Page]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    return [Page(number=1, text=soup.get_text(separator=" ", strip=True))]
