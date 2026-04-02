"""
Node 7: Answer Validator (Haiku).
1. Read-only SQL guard: scans sql_generated for write keywords.
2. Quality check: verifies the answer addresses the question.
On VALID: writes to Redis + question_logs, saves message.
On INVALID from cache: re-routes to sql. On INVALID from sql: returns error.
"""
import logging
import os
import re
import anthropic

logger = logging.getLogger(__name__)
from sqlalchemy import text
from db import SessionLocal, save_message
from embeddings import embed_question

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
DEDUP_THRESHOLD = float(os.getenv("PGVECTOR_DEDUP_THRESHOLD", 0.98))

_WRITE_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE)\b",
    re.IGNORECASE
)

_VALIDATE_SYSTEM = """You are a quality checker for database query answers.
Determine if the given answer correctly and completely addresses the question.
Reply with ONLY "VALID" or "INVALID" followed by a colon and a one-line reason.
Examples:
  VALID: answer directly states the count of users from Mumbai
  INVALID: answer talks about a different city than asked
"""


async def validate_answer(state: dict) -> dict:
    answer = state.get("answer", "")
    question = state.get("reconstructed_question", "")
    logger.info("[Validator] Validating answer for: %r", question)
    logger.info("[Validator] Answer preview: %s", answer[:120] if answer else "(empty)")
    sql = state.get("sql_generated")
    cache_source = state.get("cache_source")
    session_id = state.get("session_id")

    # 1. Read-only SQL guard
    if sql and _WRITE_PATTERN.search(sql):
        return {
            **state,
            "validated": False,
            "rejection_reason": "Write operation detected in generated SQL. Request blocked.",
            "threat": True,
        }

    # 2. Quality check
    response = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=64,
        system=_VALIDATE_SYSTEM,
        messages=[{"role": "user", "content": f"Question: {question}\n\nAnswer: {answer}"}]
    )
    verdict = response.content[0].text.strip()
    is_valid = verdict.upper().startswith("VALID")
    logger.info("[Validator] Verdict: %s", verdict)

    if not is_valid:
        logger.warning("[Validator] INVALID — cache_source=%s", state.get("cache_source"))
        return {
            **state,
            "validated": False,
            "validation_verdict": verdict,
        }

    # 3. Persist if this came from the live SQL agent
    if cache_source == "llm":
        await _persist_to_question_logs(question, answer, sql, state.get("intent"))
        from nodes.cache import write_to_redis
        await write_to_redis(question, answer)

    # 4. Save to conversation messages
    if session_id:
        save_message(
            session_id,
            role="assistant",
            content=answer,
            reconstructed_q=question,
            intent=state.get("intent"),
            cache_hit=cache_source,
        )

    return {**state, "validated": True}


def route_after_validation(state: dict) -> str:
    if state.get("validated"):
        return "done"
    # Invalid from cache → try live SQL
    if state.get("cache_source") in ("redis", "pgvector"):
        return "sql"
    return "error"


async def _persist_to_question_logs(question: str, answer: str, sql: str | None, intent: str | None):
    embedding = embed_question(question)
    emb_str = "[" + ",".join(str(x) for x in embedding) + "]"

    with SessionLocal() as db:
        # Dedup check: don't insert if near-identical question exists
        existing = db.execute(
            text("""
                SELECT id, 1 - (question_emb <=> :emb::vector) AS sim
                FROM question_logs
                WHERE answered = TRUE
                ORDER BY question_emb <=> :emb::vector
                LIMIT 1
            """),
            {"emb": emb_str}
        ).fetchone()

        if existing and float(existing.sim) >= DEDUP_THRESHOLD:
            db.execute(
                text("UPDATE question_logs SET hit_count = hit_count + 1 WHERE id = :id"),
                {"id": existing.id}
            )
        else:
            db.execute(
                text("""
                    INSERT INTO question_logs
                    (question, question_emb, intent, answered, validated, sql_generated, answer, cache_hit)
                    VALUES (:q, :emb::vector, :intent, TRUE, TRUE, :sql, :ans, 'llm')
                """),
                {"q": question, "emb": emb_str, "intent": intent, "sql": sql, "ans": answer}
            )
        db.commit()
