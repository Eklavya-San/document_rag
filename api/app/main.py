from fastapi import FastAPI
from app.config import get_settings
from app.ollama.client import OllamaClient
from app.routers import health


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Manual RAG Chatbot")
    app.state.settings = settings
    app.state.ollama = OllamaClient(settings)

    app.include_router(health.router)
    return app


app = create_app()
