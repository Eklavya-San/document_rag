from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Document, ChatSession, ChatMessage


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

    async def list_all(self, limit: int = 50, offset: int = 0) -> list[Document]:
        result = await self.session.execute(
            select(Document).order_by(Document.id.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def set_status(self, doc_id: int, status: str, **fields) -> None:
        from sqlalchemy import update
        values = {"status": status, **fields}
        await self.session.execute(
            update(Document).where(Document.id == doc_id).values(**values)
        )
        await self.session.commit()

    async def delete(self, doc_id: int) -> None:
        await self.session.execute(delete(Document).where(Document.id == doc_id))
        await self.session.commit()



class ChatRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_session(self, title: str | None = None) -> ChatSession:
        sess = ChatSession(title=title)
        self.session.add(sess)
        await self.session.commit()
        await self.session.refresh(sess)
        return sess

    async def get_session(self, session_id: int) -> ChatSession | None:
        result = await self.session.execute(select(ChatSession).where(ChatSession.id == session_id))
        return result.scalar_one_or_none()

    async def add_message(self, session_id: int, role: str, content: str, sources_json=None) -> ChatMessage:
        msg = ChatMessage(session_id=session_id, role=role, content=content, sources_json=sources_json)
        self.session.add(msg)
        await self.session.commit()
        await self.session.refresh(msg)
        return msg

    async def list_messages(self, session_id: int, limit: int, offset: int = 0) -> list[ChatMessage]:
        # last `limit` messages (after skipping `offset`), returned oldest-first
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(reversed(result.scalars().all()))
