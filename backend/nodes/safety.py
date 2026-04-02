"""
Node 01: Safety Filter.
1. Input length check (>2000 chars)
2. Text normalization (unicode homoglyphs, zero-width chars, HTML entities)
3. SQL injection detection via sqlparse AST (not regex)
4. Prompt injection detection (deterministic string matching)
5. Threat → log hash + Haiku-generated polite decline (rate-limited 1/sec/session)
6. Clean → pass to Node 02
"""
import hashlib
import html
import logging
import os
import re
import time
import unicodedata

import anthropic
import sqlparse
from sqlparse.tokens import DDL, DML, Keyword

logger = logging.getLogger(__name__)
_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Rate limit: max 1 Haiku call per second per session on threat path
_last_haiku_call: dict[str, float] = {}
_HAIKU_RATE_LIMIT_SEC = 1.0

# Prompt injection patterns (deterministic matching on normalized text)
_PROMPT_INJECTION_PATTERNS = [
    "ignore previous",
    "ignore all previous",
    "disregard previous",
    "forget everything",
    "pretend you are",
    "act as dba",
    "act as a dba",
    "roleplay as",
    "you are now",
    "your true self",
    "new persona",
    "system prompt",
    "reveal your instructions",
    "show your instructions",
    "ignore your instructions",
    "bypass",
    "jailbreak",
]

# DML/DDL tokens that indicate write operations
_DANGEROUS_TOKEN_TYPES = {DDL, DML}
_DANGEROUS_KEYWORDS = {
    "DROP", "DELETE", "TRUNCATE", "ALTER", "INSERT",
    "UPDATE", "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE",
}
_COMMENT_PATTERNS = ["--", "/*", "*/", "/**/"]
_OR_BYPASS_PATTERN = re.compile(r"\bOR\s+1\s*=\s*1\b", re.IGNORECASE)


def safety_filter(state: dict) -> dict:
    question = state.get("question", "")
    session_id = state.get("session_id", "unknown")
    author_id = state.get("user_profile", {}).get("author_id", "unknown")

    # If Node 00 had a context error, pass it through
    if state.get("context_error"):
        return {**state, "threat": True, "llm_reply": state["context_error"]}

    # ── 1. Input length check ──────────────────────────────────────────────────
    if len(question) > 2000:
        logger.warning("[Node01] Input too long (%d chars) — session %s", len(question), session_id)
        reply = _haiku_decline(session_id, "input_too_long")
        return {**state, "threat": True, "llm_reply": reply}

    # ── 2. Text normalization ──────────────────────────────────────────────────
    normalized = _normalize_text(question)

    # ── 3. SQL injection via sqlparse AST ─────────────────────────────────────
    if _detect_sql_injection_ast(normalized):
        logger.warning("[Node01] SQL injection detected — session %s", session_id)
        _log_threat_hash(author_id, question)
        reply = _haiku_decline(session_id, "sql_injection")
        return {**state, "threat": True, "llm_reply": reply}

    # ── 4. Prompt injection ────────────────────────────────────────────────────
    if _detect_prompt_injection(normalized):
        logger.warning("[Node01] Prompt injection detected — session %s", session_id)
        _log_threat_hash(author_id, question)
        reply = _haiku_decline(session_id, "prompt_injection")
        return {**state, "threat": True, "llm_reply": reply}

    logger.info("[Node01] Safety check passed — session %s", session_id)
    return {**state, "threat": False}


def is_threat(state: dict) -> str:
    return "reject" if state.get("threat") else "continue"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _normalize_text(text: str) -> str:
    """
    Normalize text to strip unicode homoglyphs, zero-width chars, HTML entities.
    Returns ASCII-safe, whitespace-normalized string.
    """
    # Decode HTML entities (&amp; → &, etc.)
    text = html.unescape(text)
    # Normalize unicode (NFKD decomposes homoglyphs like ｄ → d)
    text = unicodedata.normalize("NFKD", text)
    # Remove zero-width and invisible chars
    text = re.sub(r"[\u200b\u200c\u200d\u00ad\ufeff\u2060]", "", text)
    # Collapse excessive whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _detect_sql_injection_ast(text: str) -> bool:
    """
    Parses text with sqlparse. Returns True if dangerous DDL/DML tokens found
    OR known comment/bypass patterns detected.
    """
    # Check OR 1=1 bypass
    if _OR_BYPASS_PATTERN.search(text):
        return True

    # Check SQL comment sequences
    for pat in _COMMENT_PATTERNS:
        if pat in text:
            return True

    # Parse with sqlparse and check token types
    try:
        statements = sqlparse.parse(text)
        for stmt in statements:
            for token in stmt.flatten():
                if token.ttype in _DANGEROUS_TOKEN_TYPES:
                    if token.normalized.upper() in _DANGEROUS_KEYWORDS:
                        return True
                # Also check plain Keyword tokens
                if token.ttype is Keyword and token.normalized.upper() in _DANGEROUS_KEYWORDS:
                    return True
    except Exception:
        pass

    return False


def _detect_prompt_injection(text: str) -> bool:
    """Deterministic string matching on normalized lowercase text."""
    lower = text.lower()
    return any(pattern in lower for pattern in _PROMPT_INJECTION_PATTERNS)


def _haiku_decline(session_id: str, reason_type: str) -> str:
    """
    Generate a polite, vague decline via Haiku.
    Rate-limited: max 1 call/sec/session. Falls back to template if rate exceeded.
    """
    now = time.time()
    last = _last_haiku_call.get(session_id, 0.0)
    if now - last < _HAIKU_RATE_LIMIT_SEC:
        # Rate limit hit — use lightweight template
        return "I'm unable to process that request. Please try a different question."

    _last_haiku_call[session_id] = now
    try:
        response = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            messages=[{
                "role": "user",
                "content": (
                    "A user's message was flagged by our safety system. "
                    "Generate a single polite, friendly, non-technical sentence "
                    "declining to process it. Do not reveal what was flagged or why. "
                    "Do not mention security or databases."
                )
            }]
        )
        return response.content[0].text.strip()
    except Exception as exc:
        logger.error("[Node01] Haiku decline call failed: %s", exc)
        return "I'm not able to help with that request right now."


def _log_threat_hash(author_id, question: str):
    """Log threat hash to question_logs — never store raw question text."""
    try:
        q_hash = hashlib.sha256(question.encode()).hexdigest()
        from db import SessionLocal
        from sqlalchemy import text as sa_text
        with SessionLocal() as db:
            db.execute(
                sa_text("""
                    INSERT INTO question_logs
                        (author_id, question, answered, threat, asked_at)
                    VALUES
                        (:aid, :q, FALSE, TRUE, NOW())
                """),
                {"aid": int(author_id), "q": f"[THREAT_HASH:{q_hash[:16]}]"}
            )
            db.commit()
    except Exception as exc:
        logger.error("[Node01] Failed to log threat hash: %s", exc)
