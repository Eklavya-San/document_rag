import json


async def expand_query(question: str, ollama, n: int) -> list[str]:
    messages = [
        {
            "role": "system",
            "content": f"You rewrite a question into {n} diverse search queries. Reply ONLY with a JSON array of strings.",
        },
        {"role": "user", "content": f"Question: {question}\nReturn {n} reformulations."},
    ]
    try:
        raw = await ollama.chat(messages)
        qs = json.loads(raw)
        if isinstance(qs, list) and qs:
            return [str(q) for q in qs][:n]
    except Exception:
        pass
    return [question]


async def hyde(question: str, ollama) -> str:
    messages = [
        {
            "role": "system",
            "content": "You write a short hypothetical answer paragraph to a question. Reply with the paragraph only.",
        },
        {"role": "user", "content": f"Question: {question}"},
    ]
    try:
        return await ollama.chat(messages)
    except Exception:
        return question
