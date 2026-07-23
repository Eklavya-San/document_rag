import json
from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass
class QaItem:
    id: str
    question: str
    expected_answer: str
    expected_doc: str | None
    expected_page: int | None
    tags: list[str]


def load_qa(path: str) -> list[QaItem]:
    with open(path) as f:
        data = json.load(f)
    return [QaItem(**item) for item in data]


Pipeline = Callable[[str], Awaitable[tuple[str, list[dict]]]]


async def run_eval(pipeline: Pipeline, qa: list[QaItem], judge=None) -> list[dict]:
    results = []
    for item in qa:
        answer, sources = await pipeline(item.question)
        results.append(
            {
                "id": item.id,
                "question": item.question,
                "expected_answer": item.expected_answer,
                "answer": answer,
                "sources": sources,
                "tags": item.tags,
            }
        )
    return results
