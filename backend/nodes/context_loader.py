"""Node 0: Load conversation history + db_schema.json into state."""
import json
import os
import anthropic
from db import get_conversation_history, update_conversation_summary, SessionLocal
from sqlalchemy import text

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db_schema.json")
RECENT_COUNT = int(os.getenv("RECENT_HISTORY_COUNT", 5))
_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def load_schema() -> dict:
    if os.path.exists(SCHEMA_PATH):
        with open(SCHEMA_PATH) as f:
            return json.load(f)
    return {}


def load_context(state: dict) -> dict:
    session_id = state["session_id"]
    history = get_conversation_history(session_id, RECENT_COUNT)
    schema = load_schema()
    return {
        **state,
        "history": history,
        "schema": schema,
        "followup_count": _get_followup_count(session_id),
    }


def _get_followup_count(session_id: str) -> int:
    from db import get_followup_count
    return get_followup_count(session_id)


async def trigger_summary(session_id: str, conv_id: int):
    """Haiku call to summarize old messages. Runs as a background task."""
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
    new_summary = response.content[0].text.strip()
    update_conversation_summary(session_id, new_summary, last_msg_id)
