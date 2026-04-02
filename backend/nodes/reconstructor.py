"""
Node 2: Reconstruct + Classify + Read-Only Check (single Haiku call).
Returns: reconstructed_question, intent, rejection_reason
"""
import json
import os
import anthropic

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MAX_FOLLOWUPS = int(os.getenv("MAX_FOLLOWUPS", 2))

VALID_INTENTS = {"DB_QUERY", "META_SCHEMA", "INCOMPLETE", "SENSITIVE", "IRRELEVANT", "WRITE", "ANOMALY"}

_SYSTEM = """You are a query preprocessor for a read-only database chatbot.

Your job (single JSON response):
1. RECONSTRUCT the user's question into a clear, standalone, self-contained question.
   - Resolve pronouns using conversation history and user_profile
   - Expand abbreviations and informal language
   - If the question is already clear, return it unchanged
2. CLASSIFY the reconstructed question into one of:
   - DB_QUERY: answerable by querying the database tables
   - META_SCHEMA: asking what tables/columns/data exist
   - INCOMPLETE: too vague to answer even with reasonable inference (use sparingly — infer if possible)
   - SENSITIVE: requests restricted fields listed in sensitive_columns
   - IRRELEVANT: completely unrelated to the database (e.g. "what's the time")
   - WRITE: attempts to modify data (delete/update/insert/drop)
   - ANOMALY: gibberish or unresolvable

IMPORTANT RULES:
- This system is READ-ONLY. Any question asking to modify data must be classified WRITE.
- Only classify INCOMPLETE if the question truly cannot be answered with any reasonable interpretation.
  If an answer is fetchable, infer and proceed as DB_QUERY.
- "tell me about it" in a DB conversation context = DB_QUERY (referring to the database).
- "what's the time" / "write me a poem" = IRRELEVANT.

Respond ONLY with valid JSON, no extra text:
{
  "reconstructed": "<reconstructed question>",
  "intent": "<one of the 7 intents>",
  "rejection_reason": "<reason if not DB_QUERY/META_SCHEMA/INCOMPLETE, else null>"
}
"""


def reconstruct_and_classify(state: dict) -> dict:
    question = state["question"]
    user_profile = state.get("user_profile", {})
    history = state.get("history", {})
    schema = state.get("schema", {})
    followup_count = state.get("followup_count", 0)

    schema_summary = _build_schema_summary(schema)
    sensitive = schema.get("sensitive_columns", [])
    history_text = _format_history(history)

    user_msg = (
        f"user_profile: {json.dumps(user_profile)}\n"
        f"sensitive_columns: {sensitive}\n"
        f"available_tables_summary: {schema_summary}\n"
        f"conversation_history:\n{history_text}\n\n"
        f"raw_question: {question}"
    )

    response = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_msg}]
    )

    try:
        result = json.loads(response.content[0].text.strip())
    except (json.JSONDecodeError, IndexError):
        return {**state, "intent": "ANOMALY", "rejection_reason": "Failed to parse question."}

    intent = result.get("intent", "ANOMALY")
    reconstructed = result.get("reconstructed", question)
    rejection_reason = result.get("rejection_reason")

    # Handle INCOMPLETE with follow-up limit
    if intent == "INCOMPLETE":
        if followup_count >= MAX_FOLLOWUPS:
            return {
                **state,
                "intent": "INCOMPLETE_LIMIT",
                "reconstructed_question": reconstructed,
                "rejection_reason": "I'm unable to determine what you need. Please rephrase your question.",
            }

    return {
        **state,
        "reconstructed_question": reconstructed,
        "intent": intent,
        "rejection_reason": rejection_reason,
    }


def route_after_reconstruct(state: dict) -> str:
    intent = state.get("intent", "ANOMALY")
    if intent in ("DB_QUERY",):
        return "cache"
    if intent == "META_SCHEMA":
        return "meta"
    if intent == "INCOMPLETE":
        return "followup"
    if intent == "INCOMPLETE_LIMIT":
        return "reject"
    return "reject"  # SENSITIVE, IRRELEVANT, WRITE, ANOMALY


def _build_schema_summary(schema: dict) -> str:
    if not schema:
        return "unknown"
    tables = schema.get("tables", {})
    parts = []
    for tname, tinfo in tables.items():
        cols = list(tinfo.get("columns", {}).keys())
        parts.append(f"{tname}({', '.join(cols)})")
    return "; ".join(parts)


def _format_history(history: dict) -> str:
    summary = history.get("summary", "")
    recent = history.get("recent", [])
    lines = []
    if summary:
        lines.append(f"[Summary of earlier messages]: {summary}")
    for msg in recent:
        lines.append(f"{msg['role']}: {msg['content']}")
    return "\n".join(lines) if lines else "(no history)"
