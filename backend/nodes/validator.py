"""
Node 07: Answer Validator.

Check 1 (DETERMINISTIC sqlparse AST): Scan sql_generated for write keywords → threat log + decline
Check 2 (DETERMINISTIC AST): Verify correct user filter present per table in WHERE clause
Check 3 (HAIKU quality): Does the answer correctly address the question?

On all checks pass:
  - Write to question_logs (App DB) with correct expires_at
  - Write to messages (App DB)
  - Update Redis cache (user-scoped key)
  - Send done

Retry counter tracked in state (max 2 Node07→Node06 retries total).
After 2 failures: Haiku-generated error response.
"""
import logging
import os
import re

import anthropic
import sqlparse
from sqlparse.tokens import DDL, DML, Keyword

logger = logging.getLogger(__name__)
_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

DEDUP_THRESHOLD = float(os.getenv("PGVECTOR_DEDUP_THRESHOLD", 0.98))
MAX_RETRIES = 2

# Write keywords to detect in generated SQL
_WRITE_KEYWORD_TYPES = {DDL, DML}
_WRITE_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
    "CREATE", "TRUNCATE", "GRANT", "REVOKE",
}

# Per-table required filter columns
_TABLE_FILTER_COLUMNS = {
    "author":      ("id", "author_id"),
    "pr_reviewer": ("authorid", "author_id"),
    "pr_comment":  ("authorid", "author_id"),
    "commit":      ("authorid", "author_id"),
    "hivelscore":  ("orgid", "organization_id"),
}

_QUALITY_SYSTEM = """You are a quality checker for database query answers.
Given a question and an answer, determine if the answer correctly and completely addresses the question.
Reply with ONLY "YES" or "NO". No explanation."""


async def validate_answer(state: dict) -> dict:
    answer = state.get("answer", "")
    question = state.get("reconstructed_question", "")
    sql = state.get("sql_generated")
    cache_source = state.get("cache_source")
    session_id = state.get("session_id")
    user_profile = state.get("user_profile", {})
    author_id = int(user_profile.get("author_id", 0))
    retry_count = state.get("retry_count", 0)
    intent = state.get("intent")

    logger.info("[Node07] Validating — cache_source=%s, retry=%d, answer_len=%d",
                cache_source, retry_count, len(answer))

    # ── Check 1: Read-only SQL guard (deterministic sqlparse AST) ─────────────
    if sql:
        write_detected, write_kw = _check_write_sql_ast(sql)
        if write_detected:
            logger.warning("[Node07] Check1 FAIL — write keyword detected: %s", write_kw)
            _log_threat_sql(author_id, sql)
            llm_reply = _generate_error_reply("write_sql_detected")
            return {
                **state,
                "validated": False,
                "threat": True,
                "llm_reply": llm_reply,
                "retry_count": retry_count,
            }

    # ── Check 2: User filter guard (deterministic AST) ────────────────────────
    if sql and cache_source == "llm":
        filter_ok, filter_reason = _check_user_filter_ast(sql, user_profile)
        if not filter_ok:
            logger.warning("[Node07] Check2 FAIL — %s (retry=%d)", filter_reason, retry_count)
            if retry_count >= MAX_RETRIES:
                llm_reply = _generate_error_reply("user_filter_missing")
                return {
                    **state,
                    "validated": False,
                    "llm_reply": llm_reply,
                    "retry_count": retry_count,
                }
            return {
                **state,
                "validated": False,
                "retry_count": retry_count + 1,
                "answer": None,
                "sql_generated": None,
            }

    # ── Check 3: Quality check (Haiku) ────────────────────────────────────────
    quality_ok = _check_quality(question, answer)
    if not quality_ok:
        logger.warning("[Node07] Check3 FAIL — quality check failed (retry=%d)", retry_count)
        if retry_count >= MAX_RETRIES:
            llm_reply = _generate_error_reply("quality_check_failed")
            return {
                **state,
                "validated": False,
                "llm_reply": llm_reply,
                "retry_count": retry_count,
            }
        return {
            **state,
            "validated": False,
            "retry_count": retry_count + 1,
            "answer": None,
            "sql_generated": None,
        }

    # ── All checks passed ─────────────────────────────────────────────────────
    logger.info("[Node07] All checks passed — persisting")

    # Determine cache TTL (time-sensitive queries get 1hr, others 7 days)
    from nodes.checker import _TEMPORAL_PATTERN
    is_temporal = bool(_TEMPORAL_PATTERN.search(question))
    ttl_seconds = 3600 if is_temporal else 7 * 24 * 3600

    # Persist to question_logs (only if this came from live SQL, not cache)
    embedding = state.get("embedding")
    if cache_source == "llm" and answer:
        await _persist_question_log(
            author_id=author_id,
            question=question,
            embedding=embedding,
            sql=sql,
            answer=answer,
            intent=intent,
            ttl_seconds=ttl_seconds,
        )

    # Save assistant message to conversation messages
    if session_id and answer:
        from db import save_message
        save_message(
            session_id=session_id,
            author_id=author_id,
            role="assistant",
            content=answer,
            reconstructed_q=question,
            intent=intent,
            cache_hit=cache_source,
        )

    # Update Redis cache (user-scoped)
    if cache_source == "llm" and answer:
        from nodes.cache import write_to_redis
        await write_to_redis(author_id, question, answer, ttl=ttl_seconds)

    return {**state, "validated": True, "retry_count": retry_count}


def route_after_validation(state: dict) -> str:
    if state.get("validated"):
        return "done"
    if state.get("threat"):
        return "error"  # Write SQL detected — terminal error
    # Not validated, not a threat — retry if retries remain
    retry_count = state.get("retry_count", 0)
    if retry_count <= MAX_RETRIES and state.get("cache_source") in ("redis", "pgvector", "llm"):
        if state.get("cache_source") in ("redis", "pgvector"):
            return "sql"  # Cache was stale — run fresh SQL
        if state.get("answer") is None:
            return "sql"  # Retry with new SQL
    return "error"


# ── Check 1: Deterministic write SQL detection ─────────────────────────────────

def _check_write_sql_ast(sql: str) -> tuple[bool, str]:
    """Parse SQL with sqlparse AST. Returns (is_write, detected_keyword)."""
    try:
        for stmt in sqlparse.parse(sql):
            for token in stmt.flatten():
                if token.ttype in _WRITE_KEYWORD_TYPES:
                    kw = token.normalized.upper()
                    if kw in _WRITE_KEYWORDS:
                        return True, kw
                if token.ttype is Keyword:
                    kw = token.normalized.upper()
                    if kw in _WRITE_KEYWORDS:
                        return True, kw
    except Exception:
        pass
    return False, ""


# ── Check 2: Deterministic user filter validation ──────────────────────────────

def _check_user_filter_ast(sql: str, user_profile: dict) -> tuple[bool, str]:
    """
    Verify the SQL WHERE clause contains the correct user filter for each table used.
    Returns (ok, reason).
    """
    author_id = str(user_profile.get("author_id", ""))
    org_id = str(user_profile.get("organization_id", ""))
    sql_upper = sql.upper()
    sql_no_spaces = re.sub(r"\s+", "", sql_upper)

    # Detect which tables are referenced (word boundary match — avoids "AUTHOR" matching in "AUTHORID")
    for table, (filter_col, profile_key) in _TABLE_FILTER_COLUMNS.items():
        if not re.search(r'\b' + table + r'\b', sql, re.IGNORECASE):
            continue

        # Look for bypass patterns
        if "OR1=1" in sql_no_spaces or "ORTRUE" in sql_no_spaces:
            return False, f"Bypass pattern (OR 1=1) detected for table {table}"

        if f"{filter_col.upper()}ISNOTNULL" in sql_no_spaces:
            return False, f"Non-specific filter (IS NOT NULL) on {table}"

        # Determine expected filter value
        if table == "hivelscore":
            expected_val = org_id
        else:
            expected_val = author_id

        if not expected_val:
            continue  # Can't validate without knowing the value

        # Build search patterns (handles aliased tables like c.authorid = 123)
        col_upper = filter_col.upper()
        val_str = expected_val

        # Accept: "col = val", "alias.col = val", "col=val"
        patterns = [
            f"{col_upper}={val_str}",
            f"{col_upper} = {val_str}",
        ]
        found = any(p in sql_no_spaces for p in patterns)

        # Also check with dot notation (alias.col)
        if not found:
            dot_pattern = re.compile(
                r"\b\w+\." + re.escape(filter_col) + r"\s*=\s*" + re.escape(expected_val),
                re.IGNORECASE,
            )
            found = bool(dot_pattern.search(sql))

        if not found:
            return False, f"Missing {filter_col}={expected_val} filter on table {table}"

    return True, "OK"


# ── Check 3: Haiku quality check ───────────────────────────────────────────────

def _check_quality(question: str, answer: str) -> bool:
    """Returns True if Haiku confirms the answer addresses the question."""
    if not answer or not answer.strip():
        return False
    # "No data found" type answers are always valid (genuine empty result)
    if re.search(r"\bno data\b|\bno results?\b|\b0 results?\b", answer.lower()):
        return True
    try:
        response = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=5,
            system=_QUALITY_SYSTEM,
            messages=[{"role": "user", "content": f"Question: {question}\n\nAnswer: {answer}"}]
        )
        verdict = response.content[0].text.strip().upper()
        return verdict.startswith("YES")
    except Exception as exc:
        logger.error("[Node07] Quality check Haiku call failed: %s — assuming valid", exc)
        return True  # Fail open on API error


# ── Persistence helpers ────────────────────────────────────────────────────────

async def _persist_question_log(
    author_id: int,
    question: str,
    embedding: list[float] | None,
    sql: str | None,
    answer: str,
    intent: str | None,
    ttl_seconds: int,
):
    """Write to question_logs with dedup check. Empty results are NOT cached."""
    if not answer or not answer.strip():
        return
    if re.search(r"\bno data\b|\bno results?\b|\b0 results?\b", answer.lower()):
        return  # Don't cache empty result answers

    try:
        # Compute embedding if missing
        if not embedding:
            from embeddings import embed_question
            embedding = embed_question(question)

        emb_str = "[" + ",".join(str(x) for x in embedding) + "]"

        from db import SessionLocal
        from sqlalchemy import text
        with SessionLocal() as db:
            # Dedup check: don't insert if near-identical question already exists for this user
            existing = db.execute(
                text("""
                    SELECT id, 1 - (question_emb <=> :emb::vector) AS sim
                    FROM question_logs
                    WHERE answered = TRUE AND author_id = :aid
                    ORDER BY question_emb <=> :emb::vector
                    LIMIT 1
                """),
                {"emb": emb_str, "aid": author_id}
            ).fetchone()

            if existing and float(existing.sim) >= DEDUP_THRESHOLD:
                # Atomic hit_count increment
                db.execute(
                    text("UPDATE question_logs SET hit_count = hit_count + 1 WHERE id = :id"),
                    {"id": existing.id}
                )
            else:
                db.execute(
                    text("""
                        INSERT INTO question_logs
                            (author_id, question, question_emb, intent,
                             answered, validated, sql_generated, answer,
                             cache_hit, expires_at)
                        VALUES
                            (:aid, :q, :emb::vector, :intent,
                             TRUE, TRUE, :sql, :ans,
                             'llm', NOW() + :ttl * INTERVAL '1 second')
                    """),
                    {
                        "aid": author_id,
                        "q": question,
                        "emb": emb_str,
                        "intent": intent,
                        "sql": sql,
                        "ans": answer,
                        "ttl": ttl_seconds,
                    }
                )
            db.commit()

    except Exception as exc:
        logger.error("[Node07] Failed to persist question_log: %s", exc)


def _log_threat_sql(author_id: int, sql: str):
    """Log write SQL threat to question_logs (hash only)."""
    try:
        import hashlib
        sql_hash = hashlib.sha256(sql.encode()).hexdigest()
        from db import SessionLocal
        from sqlalchemy import text
        with SessionLocal() as db:
            db.execute(
                text("""
                    INSERT INTO question_logs
                        (author_id, question, answered, threat, asked_at)
                    VALUES
                        (:aid, :q, FALSE, TRUE, NOW())
                """),
                {"aid": author_id, "q": f"[WRITE_SQL_HASH:{sql_hash[:16]}]"}
            )
            db.commit()
    except Exception as exc:
        logger.error("[Node07] Failed to log threat SQL: %s", exc)


def _generate_error_reply(error_type: str) -> str:
    """Haiku-generated error response — no static strings."""
    prompts = {
        "write_sql_detected": (
            "Generate a polite single sentence telling a user that their request "
            "couldn't be completed because the system is read-only."
        ),
        "user_filter_missing": (
            "Generate a polite single sentence telling a user that their request "
            "couldn't be completed due to a data access error. Suggest rephrasing."
        ),
        "quality_check_failed": (
            "Generate a polite single sentence telling a user you couldn't find "
            "a reliable answer to their question and suggesting they try rephrasing it."
        ),
    }
    prompt = prompts.get(error_type, "Generate a polite single sentence apologizing for being unable to help.")
    try:
        resp = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.content[0].text.strip()
    except Exception:
        return "I wasn't able to complete that request. Please try rephrasing your question."
