import re

CITATION_RE = re.compile(r"\[([^\],]+?)(?:\s*>\s*[^,\]]+)?,\s*p\.(\d+)\]")


def citation_accuracy(answer: str, sources: list[dict]) -> float:
    matches = CITATION_RE.findall(answer)
    if not matches:
        return 0.0
    valid = {(s.get("filename"), str(s.get("page"))) for s in sources}
    correct = sum(1 for fn, pg in matches if (fn.strip(), pg) in valid)
    return correct / len(matches)
