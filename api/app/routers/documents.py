import os
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_session
from app.db.repositories import DocumentRepository
from app.ingestion.orchestrator import ingest_document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(
    request: Request,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    settings = request.app.state.settings
    os.makedirs(settings.data_dir, exist_ok=True)
    repo = DocumentRepository(session)
    doc = await repo.create(file.filename)
    save_path = os.path.join(settings.data_dir, f"{doc.id}_{file.filename}")
    with open(save_path, "wb") as f:
        f.write(await file.read())
    # The background task opens its OWN session (the request session closes with the request).
    background.add_task(_run_ingest, doc.id, save_path, file.filename, request.app)
    return _doc_dict(await repo.get(doc.id))


async def _run_ingest(doc_id: int, file_path: str, filename: str, app):
    async with app.state.session_factory() as session:
        repo = DocumentRepository(session)
        await ingest_document(
            doc_id, file_path, filename, repo,
            app.state.ollama, app.state.qdrant, app.state.settings,
        )


@router.get("")
async def list_documents(session: AsyncSession = Depends(get_session)):
    repo = DocumentRepository(session)
    return [_doc_dict(d) for d in await repo.list_all()]


@router.get("/{doc_id}")
async def get_document(doc_id: int, session: AsyncSession = Depends(get_session)):
    repo = DocumentRepository(session)
    doc = await repo.get(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    return _doc_dict(doc)


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: int, request: Request, session: AsyncSession = Depends(get_session)):
    repo = DocumentRepository(session)
    doc = await repo.get(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    await request.app.state.qdrant.delete_by_doc(doc_id)
    settings = request.app.state.settings
    save_path = os.path.join(settings.data_dir, f"{doc_id}_{doc.filename}")
    if os.path.exists(save_path):
        os.remove(save_path)
    await repo.delete(doc_id)
    return None


def _doc_dict(doc):
    return {
        "id": doc.id,
        "filename": doc.filename,
        "status": doc.status,
        "chunk_count": doc.chunk_count,
        "parser_used": doc.parser_used,
        "error": doc.error,
    }
