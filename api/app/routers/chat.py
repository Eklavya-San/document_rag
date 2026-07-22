import json
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_session
from app.db.repositories import ChatRepository
from app.rag.retriever import Retriever
from app.rag.prompt import build_messages

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str
    session_id: int | None = None


@router.post("")
async def chat(req: ChatRequest, request: Request, session: AsyncSession = Depends(get_session)):
    settings = request.app.state.settings
    repo = ChatRepository(session)

    if req.session_id:
        sess = await repo.get_session(req.session_id)
        if sess is None:
            raise HTTPException(status_code=404, detail="session not found")
    else:
        sess = await repo.create_session(title=req.question[:80])
    await repo.add_message(sess.id, "user", req.question)
    history = await repo.list_messages(sess.id, settings.chat_history_turns)
    # history is oldest-first and ends with the user message just added; drop it so the
    # current question (passed separately to build_messages) is not duplicated.
    prior_history = history[:-1]

    ollama = request.app.state.ollama
    qdrant = request.app.state.qdrant
    retriever = Retriever(ollama, qdrant, settings)

    try:
        sources = await retriever.retrieve(req.question)
    except Exception:
        raise HTTPException(status_code=503, detail="AI service unavailable")

    session_id = sess.id
    source_dicts = [_source_dict(s) for s in sources]

    if not sources:
        async def no_context():
            yield _sse({"type": "session", "session_id": session_id})
            text = "I couldn't find this in the manuals."
            yield _sse({"type": "token", "content": text})
            async with request.app.state.session_factory() as s:
                await ChatRepository(s).add_message(session_id, "assistant", text, sources_json=[])
            yield _sse({"type": "sources", "sources": []})
            yield _sse({"type": "done"})
        return StreamingResponse(no_context(), media_type="text/event-stream")

    messages = build_messages(req.question, sources, prior_history)

    async def generate():
        yield _sse({"type": "session", "session_id": session_id})
        collected = []
        async for piece in ollama.chat_stream(messages):
            collected.append(piece)
            yield _sse({"type": "token", "content": piece})
        answer = "".join(collected)
        async with request.app.state.session_factory() as s:
            await ChatRepository(s).add_message(session_id, "assistant", answer, sources_json=source_dicts)
        yield _sse({"type": "sources", "sources": source_dicts})
        yield _sse({"type": "done"})

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/sessions/{session_id}/messages")
async def list_session_messages(session_id: int, session: AsyncSession = Depends(get_session)):
    repo = ChatRepository(session)
    sess = await repo.get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session not found")
    msgs = await repo.list_messages(session_id, limit=1000)
    return [
        {"role": m.role, "content": m.content, "sources": m.sources_json or []}
        for m in msgs
    ]


def _sse(obj) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _source_dict(s) -> dict:
    return {"filename": s.filename, "page": s.page, "text": s.text, "score": s.score}
