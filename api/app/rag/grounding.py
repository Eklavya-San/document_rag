from app.rag.retriever import Source


async def check_grounding(answer: str, sources: list[Source], ollama) -> bool:
    if not sources:
        return True
    context = "\n".join(s.text[:500] for s in sources)
    messages = [
        {
            "role": "system",
            "content": "You judge whether an answer is supported ONLY by the provided context. Reply with 'yes' or 'no'.",
        },
        {
            "role": "user",
            "content": f"Context:\n{context}\n\nAnswer:\n{answer}\n\nIs the answer fully supported by the context?",
        },
    ]
    try:
        raw = (await ollama.chat(messages)).strip().lower()
        return raw.startswith("yes")
    except Exception:
        return True
