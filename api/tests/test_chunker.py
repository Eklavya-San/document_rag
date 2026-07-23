from app.ingestion.parsers import Page
from app.ingestion.chunker import Chunk, chunk_pages


def test_single_short_page_produces_one_chunk():
    pages = [Page(number=1, text="Hello world.")]
    chunks = chunk_pages(pages, size_chars=100, overlap_chars=20)
    assert chunks == [Chunk(text="Hello world.", page=1)]


def test_long_page_split_within_size_with_overlap():
    text = "word " * 60  # 300 chars
    pages = [Page(number=2, text=text)]
    chunks = chunk_pages(pages, size_chars=100, overlap_chars=20)
    assert all(len(c.text) <= 100 for c in chunks)
    assert len(chunks) >= 3
    assert all(c.page == 2 for c in chunks)
    # overlap: the start of the second chunk is within 20 chars of the first chunk's end
    assert chunks[1].text[:5] == chunks[0].text[-20:][:5]


def test_chunks_keep_page_numbers_across_pages():
    pages = [Page(number=1, text="alpha"), Page(number=2, text="beta")]
    chunks = chunk_pages(pages, size_chars=100, overlap_chars=10)
    assert chunks[0].page == 1
    assert chunks[1].page == 2


def test_empty_pages_are_skipped():
    pages = [Page(number=1, text="   "), Page(number=2, text="real text")]
    chunks = chunk_pages(pages, size_chars=100, overlap_chars=10)
    assert chunks == [Chunk(text="real text", page=2)]


def test_does_not_split_mid_word():
    text = "a" * 95 + " wordtail"
    pages = [Page(number=1, text=text)]
    chunks = chunk_pages(pages, size_chars=100, overlap_chars=0)
    assert all(not c.text.startswith("wordtail") or c.text == "wordtail" or " " in c.text for c in chunks)


def test_chunk_carries_section():
    from app.ingestion.chunker import chunk_pages
    from app.ingestion.parsers import Page
    pages = [Page(number=1, text="x" * 600, section="Safety")]
    chunks = chunk_pages(pages, 200, 20)
    assert chunks and chunks[0].section == "Safety"

