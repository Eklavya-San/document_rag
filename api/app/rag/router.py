_COMPLEX = {"explain", "compare", "why", "how", "analyze", "summarize", "difference", "versus", "vs"}


def pick_model(question: str, settings) -> str:
    if not settings.tiered_models_enabled:
        return settings.ollama_llm_model
    words = question.split()
    if len(words) <= settings.small_model_max_words and not any(w.lower().strip("?,.") in _COMPLEX for w in words):
        return settings.ollama_small_llm_model
    return settings.ollama_llm_model
