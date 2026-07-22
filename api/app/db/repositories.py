from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Document


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, filename: str) -> Document:
        doc = Document(filename=filename, status="pending")
        self.session.add(doc)
        await self.session.commit()
        await self.session.refresh(doc)
        return doc

    async def get(self, doc_id: int) -> Document | None:
        result = await self.session.execute(select(Document).where(Document.id == doc_id))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Document]:
        result = await self.session.execute(select(Document).order_by(Document.id.desc()))
        return list(result.scalars().all())

    async def set_status(self, doc_id: int, status: str, **fields) -> None:
        doc = await self.get(doc_id)
        if doc is None:
            return
        doc.status = status
        for k, v in fields.items():
            setattr(doc, k, v)
        await self.session.commit()

    async def delete(self, doc_id: int) -> None:
        await self.session.execute(delete(Document).where(Document.id == doc_id))
        await self.session.commit()
