from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Ollama (external)
    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "qwen2.5:32b"
    ollama_embed_model: str = "bge-m3"
    embed_dim: int = 1024
    ollama_num_parallel: int = 2

    # Retrieval / RAG
    chunk_size_tokens: int = 512
    chunk_overlap_tokens: int = 50
    retrieval_top_k: int = 5
    rerank_enabled: bool = False
    chat_history_turns: int = 6
    no_context_threshold: float = 0.35

    # Stores
    qdrant_url: str = "http://qdrant:6333"
    postgres_dsn: str = "postgresql+asyncpg://rag:rag@postgres:5432/rag"
    data_dir: str = "/data/manuals"

    # Auth (set in prod; empty/unset disables auth for local dev)
    api_key: str | None = None

    # Upload ceiling enforced server-side (bytes)
    max_upload_bytes: int = 200 * 1024 * 1024

    # App
    api_host: str = "0.0.0.0"
    api_port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()
