from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    settings = request.app.state.settings
    ollama = request.app.state.ollama
    ollama_status = "ok" if await ollama.ping() else "unreachable"
    return {
        "status": "ok",
        "config": {
            "ollama_base_url": settings.ollama_base_url,
            "ollama_llm_model": settings.ollama_llm_model,
            "ollama_embed_model": settings.ollama_embed_model,
            "embed_dim": settings.embed_dim,
        },
        "dependencies": {"ollama": ollama_status},
    }
