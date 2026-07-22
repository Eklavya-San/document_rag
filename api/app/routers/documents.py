import logging
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import require_api_key
from app.db.base import get_session
from app.db.repositories import DocumentRepository
from app.ingestion.orchestrator import ingest_document

router = APIRouter(prefix="/documents", tags=["documents"], dependencies=[Depends(require_api_key)])


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
    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()
    if ext not in {".pdf", ".docx", ".html", ".htm"}:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext or '(none)'}")
    safe_name = os.path.basename(filename)
    if len(safe_name) > 512:
        raise HTTPException(status_code=400, detail="filename too long")
    import uuid
    tmp_path = os.path.join(settings.data_dir, f"tmp_{uuid.uuid4().hex}_{safe_name}")
    written = 0
    try:
        with open(tmp_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > settings.max_upload_bytes:
                    raise HTTPException(status_code=413, detail="file too large")
                f.write(chunk)
    except HTTPException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise HTTPException(status_code=500, detail="upload write failed")

    # Row created only after a successful write.
    doc = await repo.create(safe_name)
    final_path = os.path.join(settings.data_dir, f"{doc.id}_{safe_name}")
    try:
        os.rename(tmp_path, final_path)
    except OSError:
        await repo.delete(doc.id)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise HTTPException(status_code=500, detail="could not finalize upload")

    background.add_task(_run_ingest, doc.id, final_path, safe_name, request.app)
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
    await repo.delete(doc_id)
    settings = request.app.state.settings
    save_path = os.path.join(settings.data_dir, f"{doc_id}_{os.path.basename(doc.filename)}")
    if os.path.exists(save_path):
        try:
            os.remove(save_path)
        except OSError:
            logging.getLogger("uvicorn.error").warning("could not remove file %s", save_path)
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
