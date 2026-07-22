from app.config import get_settings


def test_settings_reads_env_defaults(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://gpu-box:11434")
    monkeypatch.setenv("OLLAMA_LLM_MODEL", "command-r35b")
    monkeypatch.setenv("EMBED_DIM", "768")
    monkeypatch.setenv("RERANK_ENABLED", "true")
    s = get_settings()
    assert s.ollama_base_url == "http://gpu-box:11434"
    assert s.ollama_llm_model == "command-r35b"
    assert s.embed_dim == 768
    assert s.rerank_enabled is True
    assert s.retrieval_top_k == 5  # default retained


def test_postgres_dsn_env_override(monkeypatch):
    monkeypatch.setenv("POSTGRES_DSN", "postgresql+asyncpg://u:p@h:5432/d")
    from app.config import get_settings
    get_settings.cache_clear()
    s = get_settings()
    assert s.postgres_dsn == "postgresql+asyncpg://u:p@h:5432/d"
