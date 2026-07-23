def mine_hard_negatives(results: list[dict], score_threshold: float = 0.85) -> list[dict]:
    flagged = []
    for r in results:
        if r.get("context_precision", 1.0) > 0.0:
            continue
        for s in r.get("sources", []):
            if s.get("score", 0) >= score_threshold:
                flagged.append(
                    {
                        "question_id": r["id"],
                        "chunk_id": s.get("chunk_id"),
                        "filename": s.get("filename"),
                        "page": s.get("page"),
                        "score": s.get("score"),
                    }
                )
    return flagged
