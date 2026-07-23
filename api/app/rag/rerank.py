import json
from app.rag.retriever import Source


async def rerank(question: str, sources: list[Source], ollama, top_k: int) -> list[Source]:
    if not sources:
        return sources
    numbered = "\n".join(f"{i}: {s.text[:500]}" for i, s in enumerate(sources))
    messages = [
        {
            "role": "system",
            "content": 'You score document chunks for relevance to a question. Reply ONLY with JSON: {"scores": [<float 0..1> per chunk]}.',
        },
        {
            "role": "user",
            "content": f"Question: {question}\nChunks:\n{numbered}\nReturn the scores array.",
        },
    ]
    try:
        raw = await ollama.chat(messages)
        data = json.loads(raw)
        scores = [float(x) for x in data.get("scores", [])][: len(sources)]
    except Exception:
        return sources[:top_k]
    if len(scores) != len(sources):
        return sources[:top_k]
    paired = sorted(zip(scores, sources), key=lambda x: x[0], reverse=True)
    return [s for _, s in paired[:top_k]]
