import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True)
    session_id = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    title = Column(Text)
    is_deleted = Column(Boolean, default=False)
    history_summary = Column(Text, default="")
    summarized_until_msg_id = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    role = Column(String(20), nullable=False)
    raw_question = Column(Text)
    reconstructed_q = Column(Text)
    content = Column(Text, nullable=False)
    intent = Column(String(50))
    cache_hit = Column(String(20))
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


# ── CRUD helpers ──────────────────────────────────────────────────────────────

def get_or_create_conversation(session_id: str) -> int:
    with SessionLocal() as db:
        row = db.execute(
            text("SELECT id FROM conversations WHERE session_id = :sid AND is_deleted = FALSE"),
            {"sid": session_id}
        ).fetchone()
        if row:
            return row[0]
        result = db.execute(
            text("INSERT INTO conversations (session_id) VALUES (:sid) RETURNING id"),
            {"sid": session_id}
        )
        db.commit()
        return result.fetchone()[0]


def get_conversation_history(session_id: str, recent_count: int) -> dict:
    """Returns {summary, recent} for Node 2 context input."""
    with SessionLocal() as db:
        conv = db.execute(
            text("SELECT id, history_summary, summarized_until_msg_id FROM conversations WHERE session_id = :sid AND is_deleted = FALSE"),
            {"sid": session_id}
        ).fetchone()
        if not conv:
            return {"summary": "", "recent": []}

        conv_id, summary, last_summarized_id = conv

        recent = db.execute(
            text("""
                SELECT role, content, intent FROM messages
                WHERE conversation_id = :cid AND is_deleted = FALSE
                ORDER BY id DESC LIMIT :n
            """),
            {"cid": conv_id, "n": recent_count}
        ).fetchall()

        return {
            "summary": summary or "",
            "recent": [{"role": r.role, "content": r.content, "intent": r.intent} for r in reversed(recent)]
        }


def save_message(session_id: str, role: str, content: str, **kwargs) -> int:
    conv_id = get_or_create_conversation(session_id)
    with SessionLocal() as db:
        result = db.execute(
            text("""
                INSERT INTO messages (conversation_id, role, content, raw_question, reconstructed_q, intent, cache_hit)
                VALUES (:cid, :role, :content, :raw, :recon, :intent, :cache)
                RETURNING id
            """),
            {
                "cid": conv_id,
                "role": role,
                "content": content,
                "raw": kwargs.get("raw_question"),
                "recon": kwargs.get("reconstructed_q"),
                "intent": kwargs.get("intent"),
                "cache": kwargs.get("cache_hit"),
            }
        )
        db.commit()
        msg_id = result.fetchone()[0]
    maybe_summarize(session_id, conv_id)
    return msg_id


def get_message_count_since_summary(conv_id: int, last_summarized_id: int) -> int:
    with SessionLocal() as db:
        row = db.execute(
            text("SELECT COUNT(*) FROM messages WHERE conversation_id = :cid AND id > :lid AND is_deleted = FALSE"),
            {"cid": conv_id, "lid": last_summarized_id}
        ).fetchone()
        return row[0]


def update_conversation_summary(session_id: str, summary: str, last_msg_id: int):
    with SessionLocal() as db:
        db.execute(
            text("UPDATE conversations SET history_summary = :s, summarized_until_msg_id = :mid WHERE session_id = :sid"),
            {"s": summary, "mid": last_msg_id, "sid": session_id}
        )
        db.commit()


def soft_delete_conversation(session_id: str):
    with SessionLocal() as db:
        db.execute(
            text("UPDATE conversations SET is_deleted = TRUE WHERE session_id = :sid"),
            {"sid": session_id}
        )
        db.commit()


def get_followup_count(session_id: str) -> int:
    with SessionLocal() as db:
        conv = db.execute(
            text("SELECT id FROM conversations WHERE session_id = :sid AND is_deleted = FALSE"),
            {"sid": session_id}
        ).fetchone()
        if not conv:
            return 0
        row = db.execute(
            text("SELECT COUNT(*) FROM messages WHERE conversation_id = :cid AND intent = 'INCOMPLETE' AND is_deleted = FALSE"),
            {"cid": conv[0]}
        ).fetchone()
        return row[0]


def maybe_summarize(session_id: str, conv_id: int):
    """Triggers async summary if threshold reached. Called after every message save."""
    threshold = int(os.getenv("SUMMARY_THRESHOLD", 10))
    with SessionLocal() as db:
        conv = db.execute(
            text("SELECT summarized_until_msg_id FROM conversations WHERE id = :cid"),
            {"cid": conv_id}
        ).fetchone()
        last_id = conv[0] if conv else 0

    count = get_message_count_since_summary(conv_id, last_id)
    if count >= threshold:
        # Import here to avoid circular import
        from nodes.context_loader import trigger_summary
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(trigger_summary(session_id, conv_id))
        except RuntimeError:
            pass  # Not in async context — summary will happen on next cycle
