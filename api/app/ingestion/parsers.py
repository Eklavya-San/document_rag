from dataclasses import dataclass
from pathlib import Path
from bs4 import BeautifulSoup
from pypdf import PdfReader


@dataclass
class Page:
    number: int
    text: str
    section: str = ""


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
        doc = DocxDocument(path)
    paragraphs = [p for p in doc.paragraphs if p.text.strip()]
    if not paragraphs:
        return []
    has_headings = any(p.style and p.style.name and p.style.name.startswith("Heading") for p in paragraphs)
    if not has_headings:
        text = "\n".join(p.text for p in paragraphs)
        return [Page(number=1, text=text, section="")]

    pages: list[Page] = []
    current_section = ""
    current_texts = []
    for p in paragraphs:
        if p.style and p.style.name and p.style.name.startswith("Heading"):
            if current_texts:
                pages.append(Page(number=len(pages) + 1, text="\n".join(current_texts), section=current_section))
                current_texts = []
            current_section = p.text.strip()
        else:
            current_texts.append(p.text)
    if current_texts:
        pages.append(Page(number=len(pages) + 1, text="\n".join(current_texts), section=current_section))
    return pages or [Page(number=1, text="")]


def _parse_html(path: str) -> list[Page]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    headings = soup.find_all(["h1", "h2", "h3"])
    if not headings:
        return [Page(number=1, text=soup.get_text(separator=" ", strip=True), section="")]
    pages: list[Page] = []
    section = ""
    for el in soup.find_all(["h1", "h2", "h3", "p", "li"]):
        if el.name in ("h1", "h2", "h3"):
            section = el.get_text(strip=True)
            continue
        txt = el.get_text(" ", strip=True)
        if txt:
            pages.append(Page(number=len(pages) + 1, text=txt, section=section))
    if not pages:
        pages = [Page(number=1, text=soup.get_text(separator=" ", strip=True), section="")]
    return pages
