"""
Node 03+04: Redis L1 (exact hash, user-scoped) + pgvector L2 (semantic ANN, user-scoped).
Both run in parallel via asyncio. Redis wins on speed (~1ms); pgvector is fallback.
Cache key includes author_id to prevent cross-user cache leakage.
Checks expires_at to discard stale time-sensitive answers.
"""
import asyncio
import hashlib
import logging
import os

import redis.asyncio as aioredis
from sqlalchemy import text

from db import SessionLocal
from embeddings import embed_question

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_TTL = int(os.getenv("REDIS_TTL", 3600))
SIM_THRESHOLD = float(os.getenv("PGVECTOR_SIMILARITY_THRESHOLD", 0.85))

_redis_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis_pool


def _cache_key(author_id: int, question: str) -> str:
    """User-scoped SHA-256 key — author_id prevents cross-user cache hits."""
    raw = f"{author_id}|{question.lower().strip()}"
    return "chatbot:" + hashlib.sha256(raw.encode()).hexdigest()


async def _redis_lookup(author_id: int, question: str) -> str | None:
    try:
        r = await get_redis()
        return await asyncio.wait_for(r.get(_cache_key(author_id, question)), timeout=0.1)
    except Exception as exc:
        logger.warning("[Node03] Redis lookup failed: %s — skipping L1 cache", exc)
        return None


def _pgvector_lookup_sync(author_id: int, embedding: list[float]) -> list[dict]:
    """Sync pgvector ANN query — runs in executor to avoid blocking event loop."""
    emb_str = "[" + ",".join(str(x) for x in embedding) + "]"
    with SessionLocal() as db:
        rows = db.execute(
            text("""
                SELECT id, question, answer, sql_generated,
                       1 - (question_emb <=> :emb::vector) AS similarity
                FROM question_logs
                WHERE answered = TRUE
                  AND validated = TRUE
                  AND author_id = :aid
                  AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY question_emb <=> :emb::vector
                LIMIT 5
            """),
            {"emb": emb_str, "aid": author_id}
        ).fetchall()

    return [
        {
            "id": r.id,
            "question": r.question,
            "answer": r.answer,
            "sql_generated": r.sql_generated,
            "similarity": float(r.similarity),
        }
        for r in rows
        if float(r.similarity) >= SIM_THRESHOLD
    ]


async def _pgvector_lookup(author_id: int, embedding: list[float]) -> list[dict]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _pgvector_lookup_sync, author_id, embedding)


async def cache_lookup(state: dict) -> dict:
    question = state["reconstructed_question"]
    author_id = int(state["user_profile"]["author_id"])
    embedding = state.get("embedding")

    logger.info("[Node03] Cache lookup for author=%s: %r", author_id, question)

    # ── L1: Redis (exact match, user-scoped) ──────────────────────────────────
    redis_task = asyncio.create_task(_redis_lookup(author_id, question))

    # ── L2: pgvector ANN (semantic, user-scoped) ─────────────────────────────
    # Compute embedding if Node 02 failed to do so
    if not embedding:
        try:
            embedding = embed_question(question)
            logger.info("[Node03] Re-computed embedding (Node02 missed it)")
        except Exception as exc:
            logger.warning("[Node03] Embedding failed: %s — skipping pgvector", exc)
            embedding = None

    pgvec_task = None
    if embedding:
        pgvec_task = asyncio.create_task(_pgvector_lookup(author_id, embedding))

    # ── Redis result ──────────────────────────────────────────────────────────
    redis_result = await redis_task
    if redis_result:
        if pgvec_task:
            pgvec_task.cancel()
        logger.info("[Node03] Redis HIT for author=%s", author_id)
        return {
            **state,
            "embedding": embedding,
            "cache_source": "redis",
            "answer": redis_result,
            "candidates": [],
        }

    # ── pgvector result ───────────────────────────────────────────────────────
    candidates = []
    if pgvec_task:
        try:
            candidates = await asyncio.wait_for(pgvec_task, timeout=0.5)
        except (asyncio.TimeoutError, Exception) as exc:
            logger.warning("[Node03] pgvector lookup failed: %s", exc)

    if candidates:
        logger.info("[Node03] pgvector HIT — %d candidates for author=%s", len(candidates), author_id)
        return {
            **state,
            "embedding": embedding,
            "cache_source": "pgvector",
            "candidates": candidates,
            "answer": None,
        }

    logger.info("[Node03] Cache MISS — routing to SQL agent")
    return {
        **state,
        "embedding": embedding,
        "cache_source": None,
        "candidates": [],
        "answer": None,
    }


async def write_to_redis(author_id: int, question: str, answer: str, ttl: int = REDIS_TTL):
    """Write answer to Redis with user-scoped key."""
    try:
        r = await get_redis()
        await r.setex(_cache_key(author_id, question), ttl, answer)
    except Exception as exc:
        logger.warning("[Node03] Redis write failed: %s", exc)


def route_after_cache(state: dict) -> str:
    if state.get("cache_source") == "redis":
        return "validate"
    if state.get("candidates"):
        return "check"
    return "sql"
