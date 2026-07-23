from typing import Awaitable, Callable

Judge = Callable[[list[dict]], Awaitable[str]]


def _norm_yes_no(raw: str) -> float:
    r = (raw or "").strip().lower()
    return 1.0 if r.startswith("yes") else 0.0


async def context_precision(question: str, sources: list[dict], judge: Judge) -> float:
    if not sources:
        return 0.0
    ctx = "\n".join(f"{i}: {s.get('text','')[:300]}" for i, s in enumerate(sources))
    msg = [
        {
            "role": "system",
            "content": "You judge if retrieved chunks are relevant to a question. Reply 'yes' or 'no'.",
        },
        {
            "role": "user",
            "content": f"Question: {question}\nChunks:\n{ctx}\nAre these chunks relevant?",
        },
    ]
    return _norm_yes_no(await judge(msg))


async def context_recall(
    question: str, expected_answer: str, sources: list[dict], judge: Judge
) -> float:
    if not sources:
        return 0.0
    ctx = "\n".join(s.get("text", "")[:300] for s in sources)
    msg = [
        {
            "role": "system",
            "content": "You judge if the context contains the information needed to answer. Reply 'yes' or 'no'.",
        },
        {
            "role": "user",
            "content": f"Question: {question}\nExpected answer: {expected_answer}\nContext:\n{ctx}\nIs the needed information present?",
        },
    ]
    return _norm_yes_no(await judge(msg))


async def faithfulness(answer: str, sources: list[dict], judge: Judge) -> float:
    ctx = "\n".join(s.get("text", "")[:300] for s in sources)
    msg = [
        {
            "role": "system",
            "content": "You judge if an answer is supported ONLY by the context. Reply 'yes' or 'no'.",
        },
        {
            "role": "user",
            "content": f"Context:\n{ctx}\nAnswer:\n{answer}\nIs the answer fully supported by the context?",
        },
    ]
    return _norm_yes_no(await judge(msg))


async def answer_relevance(question: str, answer: str, judge: Judge) -> float:
    msg = [
        {
            "role": "system",
            "content": "You judge if an answer addresses the question. Reply 'yes' or 'no'.",
        },
        {
            "role": "user",
            "content": f"Question: {question}\nAnswer:\n{answer}\nDoes the answer address the question?",
        },
    ]
    return _norm_yes_no(await judge(msg))


async def score(results: list[dict], judge: Judge) -> list[dict]:
    scored = []
    for r in results:
        cp = await context_precision(r["question"], r["sources"], judge)
        cr = await context_recall(
            r["question"], r["expected_answer"], r["sources"], judge
        )
        f = await faithfulness(r["answer"], r["sources"], judge)
        ar = await answer_relevance(r["question"], r["answer"], judge)
        scored.append(
            {
                **r,
                "context_precision": cp,
                "context_recall": cr,
                "faithfulness": f,
                "answer_relevance": ar,
            }
        )
    return scored
