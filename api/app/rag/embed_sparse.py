from functools import lru_cache


@lru_cache(maxsize=1)
def _model(name: str):
    from fastembed import SparseTextEmbedding
    return SparseTextEmbedding(model_name=name)


def sparse_embed(texts: list[str], model_name: str) -> list[dict]:
    model = _model(model_name)
    out = []
    for t in texts:
        sv = next(model.query_embed(t))
        out.append({"indices": list(sv.indices), "values": list(sv.values)})
    return out
