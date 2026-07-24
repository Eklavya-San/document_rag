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
    hybrid_enabled: bool = False
    sparse_model: str = "Qdrant/bm42-all-minilm-l6-v2-attentions"
    query_expansion_enabled: bool = False
    hyde_enabled: bool = False
    num_subqueries: int = 3
    tiered_models_enabled: bool = False
    ollama_small_llm_model: str = "qwen2.5:3b"
    small_model_max_words: int = 8
    grounding_check_enabled: bool = False
    embed_cache_enabled: bool = False
    cost_tracking_enabled: bool = False
    eval_qa_path: str = "app/eval/qa_pairs.json"



    embed_cache_size: int = 1024
    context_dedup_enabled: bool = False
    dedup_enabled: bool = False
    token_accurate_chunking: bool = False



    chunk_size_tokens: int = 512

    chunk_overlap_tokens: int = 50
    retrieval_top_k: int = 5
    rerank_enabled: bool = False
    rerank_top_k: int = 4
    chat_history_turns: int = 6
    no_context_threshold: float = 0.35




    # Stores
    qdrant_url: str = "http://qdrant:6333"
    postgres_dsn: str = "postgresql+asyncpg://rag:rag@postgres:5432/rag"
    data_dir: str = "/data/manuals"

    # Auth (set in prod; empty/unset disables auth for local dev)
    api_key: str | None = None

    # Chat input length bound
    max_question_chars: int = 4000

    # Rate limits
    chat_rate_limit: str = "60/minute"
    upload_rate_limit: str = "20/minute"

    # Upload ceiling enforced server-side (bytes)
    max_upload_bytes: int = 200 * 1024 * 1024

    # DOCX decompression bomb guard (bytes)
    docx_max_decompressed_bytes: int = 100 * 1024 * 1024

    # App
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Logging
    log_level: str = "INFO"
    log_file_path: str = "logs/app.log"
    log_rotation: str = "10 MB"
    log_retention: str = "14 days"


@lru_cache
def get_settings() -> Settings:
    return Settings()
