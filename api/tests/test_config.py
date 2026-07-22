import os
from app.config import get_settings


def test_settings_reads_env_defaults():
    os.environ["OLLAMA_BASE_URL"] = "http://gpu-box:11434"
    os.environ["OLLAMA_LLM_MODEL"] = "command-r35b"
    os.environ["EMBED_DIM"] = "768"
    os.environ["RERANK_ENABLED"] = "true"
    s = get_settings()
    assert s.ollama_base_url == "http://gpu-box:11434"
    assert s.ollama_llm_model == "command-r35b"
    assert s.embed_dim == 768
    assert s.rerank_enabled is True
    assert s.retrieval_top_k == 5  # default retained
