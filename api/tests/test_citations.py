from app.eval.citations import citation_accuracy


def test_all_citations_match_returns_one():
    sources = [{"filename": "m.pdf", "page": 3}]
    answer = "Calibrate per [m.pdf, p.3] and [m.pdf, p.3]."
    assert citation_accuracy(answer, sources) == 1.0


def test_mismatched_citation_lowers_score():
    sources = [{"filename": "m.pdf", "page": 3}]
    answer = "See [m.pdf, p.3] and [other.pdf, p.9]."
    assert citation_accuracy(answer, sources) == 0.5


def test_no_citations_returns_zero():
    assert (
        citation_accuracy("no citations here", [{"filename": "m.pdf", "page": 3}])
        == 0.0
    )
