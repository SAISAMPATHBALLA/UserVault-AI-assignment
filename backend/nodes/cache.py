"""
Node 3+4: Redis L1 (exact hash) + pgvector L2 (semantic, top-5) running in parallel.
Redis wins on speed (~1ms). If Redis hits, pgvector task is cancelled.
"""
import asyncio
import hashlib
import os
import json
import redis.asyncio as aioredis
from sqlalchemy import text
from db import SessionLocal
from embeddings import embed_question

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_TTL = int(os.getenv("REDIS_TTL", 3600))
SIM_THRESHOLD = float(os.getenv("PGVECTOR_SIMILARITY_THRESHOLD", 0.85))

_redis_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis_pool


def _cache_key(question: str) -> str:
    return "chatbot:" + hashlib.sha256(question.lower().strip().encode()).hexdigest()


async def _redis_lookup(question: str) -> str | None:
    r = await get_redis()
    return await r.get(_cache_key(question))


async def _pgvector_lookup(question: str) -> list[dict]:
    embedding = embed_question(question)
    emb_str = "[" + ",".join(str(x) for x in embedding) + "]"
    with SessionLocal() as db:
        rows = db.execute(
            text("""
                SELECT id, question, answer, 1 - (question_emb <=> :emb::vector) AS similarity
                FROM question_logs
                WHERE answered = TRUE AND validated = TRUE
                ORDER BY question_emb <=> :emb::vector
                LIMIT 5
            """),
            {"emb": emb_str}
        ).fetchall()
    return [
        {"id": r.id, "question": r.question, "answer": r.answer, "similarity": float(r.similarity)}
        for r in rows
        if float(r.similarity) >= SIM_THRESHOLD
    ]


async def cache_lookup(state: dict) -> dict:
    question = state["reconstructed_question"]

    redis_task = asyncio.create_task(_redis_lookup(question))
    pgvector_task = asyncio.create_task(_pgvector_lookup(question))

    # Wait for Redis first (it's faster)
    redis_result = await redis_task
    if redis_result:
        pgvector_task.cancel()
        return {
            **state,
            "cache_source": "redis",
            "answer": redis_result,
            "candidates": [],
        }

    candidates = await pgvector_task
    if candidates:
        return {**state, "cache_source": "pgvector", "candidates": candidates, "answer": None}

    return {**state, "cache_source": None, "candidates": [], "answer": None}


async def write_to_redis(question: str, answer: str):
    r = await get_redis()
    await r.setex(_cache_key(question), REDIS_TTL, answer)


def route_after_cache(state: dict) -> str:
    if state.get("cache_source") == "redis":
        return "validate"
    if state.get("candidates"):
        return "check"
    return "sql"
