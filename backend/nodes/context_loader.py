"""
Node 00: Load Context.
- Validate user_profile fields
- Validate session_id belongs to this author_id (session hijack prevention)
- Load schema from in-memory schema_cache
- Load rolling history from App DB (last 5 messages + summary)
- Create conversation row if new session
"""
import logging
import os
import anthropic
from db import (
    get_or_create_conversation, get_conversation_history,
    update_conversation_summary, validate_session_author, SessionLocal,
)
from sqlalchemy import text
import schema_cache

logger = logging.getLogger(__name__)
RECENT_COUNT = int(os.getenv("RECENT_HISTORY_COUNT", 5))
_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

_REQUIRED_PROFILE_FIELDS = {
    "author_id": int,
    "account_id": str,
    "organization_id": int,
    "name": str,
    "timezone": str,
}


def load_context(state: dict) -> dict:
    session_id = state["session_id"]
    user_profile = state.get("user_profile", {})

    # ── 1. Validate required user_profile fields ───────────────────────────────
    validation_error = _validate_user_profile(user_profile)
    if validation_error:
        logger.warning("[Node00] user_profile validation failed: %s", validation_error)
        return {**state, "context_error": validation_error}
    author_id = int(user_profile["author_id"])

    # ── 2. Session → author_id validation (session hijack prevention) ──────────
    if not validate_session_author(session_id, author_id):
        logger.warning("[Node00] Session hijack attempt: session %s does not belong to author %s",
                       session_id, author_id)
        return {**state, "context_error": "Session does not belong to this user."}

    # ── 3. Create conversation row if new session ──────────────────────────────
    get_or_create_conversation(session_id, author_id)

    # ── 4. Load schema from in-memory cache (never disk I/O per request) ───────
    current_schema = schema_cache.get_schema()
    if not current_schema:
        logger.error("[Node00] Schema cache is empty — Source DB may have been unavailable at startup")
        return {**state, "context_error": "System schema not available. Please try again later."}

    # ── 5. Load rolling history from App DB ───────────────────────────────────
    history = get_conversation_history(session_id, RECENT_COUNT)
    followup_count = _get_followup_count(session_id)

    logger.info("[Node00] Context loaded — author_id=%s, history msgs=%d, followup_count=%d",
                author_id, len(history.get("recent", [])), followup_count)

    return {
        **state,
        "history": history,
        "schema": current_schema,
        "followup_count": followup_count,
        "context_error": None,
    }

def _validate_user_profile(profile: dict) -> str | None:
    """Returns error message if validation fails, None if OK."""
    for field, expected_type in _REQUIRED_PROFILE_FIELDS.items():
        if field not in profile or profile[field] is None:
            return f"Missing required field: {field}"
        try:
            expected_type(profile[field])
        except (ValueError, TypeError):
            return f"Invalid type for field '{field}': expected {expected_type.__name__}"
    return None


def _get_followup_count(session_id: str) -> int:
    from db import get_followup_count
    return get_followup_count(session_id)


async def trigger_summary(session_id: str, conv_id: int):
    """Haiku call to summarize old messages. Runs as background task."""
    with SessionLocal() as db:
        conv = db.execute(
            text("SELECT summarized_until_msg_id, history_summary FROM conversations WHERE id = :cid"),
            {"cid": conv_id}
        ).fetchone()
        last_id, existing_summary = conv[0], conv[1] or ""

        messages = db.execute(
            text("""
                SELECT role, content FROM messages
                WHERE conversation_id = :cid AND id > :lid AND is_deleted = FALSE
                ORDER BY id ASC
            """),
            {"cid": conv_id, "lid": last_id}
        ).fetchall()

        last_msg_id = db.execute(
            text("SELECT MAX(id) FROM messages WHERE conversation_id = :cid"),
            {"cid": conv_id}
        ).fetchone()[0]

    if not messages:
        return

    history_text = "\n".join(f"{m.role}: {m.content}" for m in messages)
    prompt = (
        f"Existing summary: {existing_summary}\n\n"
        f"New messages to incorporate:\n{history_text}\n\n"
        "Write a concise updated summary preserving all key facts, entities, and context. "
        "Be brief but complete."
    )

    response = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}]
    )
    logger.info("[Node00] LLM response — fn=trigger_summary in=%d out=%d stop=%s text=%r",
                response.usage.input_tokens, response.usage.output_tokens,
                response.stop_reason, response.content[0].text[:120])
    new_summary = response.content[0].text.strip()
    update_conversation_summary(session_id, new_summary, last_msg_id)
