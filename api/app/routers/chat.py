import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.rate import limiter
from app.auth import require_api_key
from app.db.base import get_session
from app.db.repositories import ChatRepository
from app.rag.retriever import Retriever
from app.rag.prompt import build_messages

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(require_api_key)])


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    session_id: int | None = None
    filename: str | None = None
    doc_ids: list[int] | None = None


@router.post("")
@limiter.limit(lambda: get_settings().chat_rate_limit)
async def chat(req: ChatRequest, request: Request):

    settings = request.app.state.settings
    if len(req.question) > settings.max_question_chars:
        raise HTTPException(status_code=422, detail="question too long")

    # Validate existing session + fetch prior history in a short-lived session.
    prior_history: list = []
    if req.session_id:
        async with request.app.state.session_factory() as session:
            repo = ChatRepository(session)
            sess = await repo.get_session(req.session_id)
            if sess is None:
                raise HTTPException(status_code=404, detail="session not found")
            prior_history = await repo.list_messages(req.session_id, settings.chat_history_turns)

    from qdrant_client.http import models as qm
    must = []
    if req.filename:
        must.append(qm.FieldCondition(key="filename", match=qm.MatchValue(value=req.filename)))
    if req.doc_ids:
        must.append(qm.FieldCondition(key="doc_id", match=qm.MatchAny(any=req.doc_ids)))
    query_filter = qm.Filter(must=must) if must else None

    # Retrieval BEFORE committing the user message, so a 503 leaves no orphan.
    ollama = request.app.state.ollama
    qdrant = request.app.state.qdrant
    retriever = Retriever(ollama, qdrant, settings, judge=ollama)

    from app.observability import timed
    try:
        async with timed("retrieval"):
            sources = await retriever.retrieve(req.question, query_filter=query_filter)
    except Exception:

        logging.getLogger("uvicorn.error").exception("chat retrieval failed")
        raise HTTPException(status_code=503, detail="AI service unavailable")


    # Create/fetch session + commit user message in a short-lived session.
    async with request.app.state.session_factory() as session:
        repo = ChatRepository(session)
        if req.session_id:
            sess = await repo.get_session(req.session_id)
            if sess is None:
                raise HTTPException(status_code=404, detail="session not found")
            session_id = sess.id
        else:
            sess = await repo.create_session(title=req.question[:80])
            session_id = sess.id
        await repo.add_message(session_id, "user", req.question)

    source_dicts = [_source_dict(s) for s in sources]

    if not sources:
        async def no_context():
            yield _sse({"type": "session", "session_id": session_id})
            text = "I couldn't find this in the manuals."
            yield _sse({"type": "token", "content": text})
            try:
                async with request.app.state.session_factory() as s:
                    await ChatRepository(s).add_message(session_id, "assistant", text, sources_json=[])
            except Exception:
                logging.getLogger("uvicorn.error").exception("failed to persist assistant message")
            yield _sse({"type": "sources", "sources": []})
            yield _sse({"type": "done"})
        return StreamingResponse(no_context(), media_type="text/event-stream")

    from app.rag.router import pick_model
    model = pick_model(req.question, settings)
    messages = build_messages(req.question, sources, prior_history)

    async def generate():
        yield _sse({"type": "session", "session_id": session_id})
        collected: list[str] = []
        try:
            async for piece in ollama.chat_stream(messages, model=model):

                collected.append(piece)
                yield _sse({"type": "token", "content": piece})
        except Exception:
            logging.getLogger("uvicorn.error").exception("chat stream failed")
        finally:
            answer = "".join(collected)
            grounded = None
            if settings.grounding_check_enabled:
                from app.rag.grounding import check_grounding
                try:
                    grounded = await check_grounding(answer, sources, ollama)
                except Exception:
                    grounded = None
            tokens = None
            if settings.cost_tracking_enabled:
                try:
                    import tiktoken
                    tokens = len(tiktoken.get_encoding("cl100k_base").encode(answer))
                except Exception:
                    tokens = None
            try:
                async with request.app.state.session_factory() as s:
                    await ChatRepository(s).add_message(session_id, "assistant", answer, sources_json=source_dicts, grounded=grounded, tokens=tokens)
            except Exception:
                logging.getLogger("uvicorn.error").exception("failed to persist assistant message")
            if grounded is False:
                yield _sse({"type": "token", "content": "\n\n_(note: this answer could not be fully verified against the source documents.)_"})

        yield _sse({"type": "sources", "sources": source_dicts})
        yield _sse({"type": "done"})

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/sessions/{session_id}/messages")
async def list_session_messages(
    session_id: int,
    limit: int = 1000,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    repo = ChatRepository(session)
    sess = await repo.get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session not found")
    msgs = await repo.list_messages(session_id, limit=limit, offset=offset)
    return [
        {"id": m.id, "role": m.role, "content": m.content, "sources": m.sources_json or [], "tokens": m.tokens}
        for m in msgs
    ]


class FeedbackRequest(BaseModel):
    rating: int
    correction: str | None = None
    clicked_source_ids: list[str] | None = None


@router.post("/messages/{message_id}/feedback", status_code=204)
async def post_feedback(message_id: int, body: FeedbackRequest, session: AsyncSession = Depends(get_session)):
    if body.rating not in (1, -1):
        raise HTTPException(status_code=422, detail="rating must be 1 or -1")
    from app.db.repositories import FeedbackRepository
    await FeedbackRepository(session).add(message_id, body.rating, body.correction, body.clicked_source_ids)
    return None




def _sse(obj) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _source_dict(s) -> dict:
    return {"filename": s.filename, "page": s.page, "text": s.text, "score": s.score, "chunk_id": s.chunk_id}
