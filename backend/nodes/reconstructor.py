"""
Node 02: Reconstruct + Classify + Reply Generator.
Single Haiku call → structured JSON output.
- Reconstructs question into self-contained form
- Classifies intent: DB_QUERY | INCOMPLETE | SENSITIVE | IRRELEVANT | CONVERSATIONAL | WRITE
- Generates LLM reply for non-DB intents (ZERO static strings to user)
- Computes embedding for DB_QUERY questions (once, stored in state for reuse)
- Extracts tables_hint for Node 06 acceleration
"""
import json
import logging
import os
import re

import anthropic

from embeddings import embed_question

logger = logging.getLogger(__name__)
_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MAX_FOLLOWUPS = int(os.getenv("MAX_FOLLOWUPS", 2))

VALID_INTENTS = {"DB_QUERY", "INCOMPLETE", "SENSITIVE", "IRRELEVANT", "CONVERSATIONAL", "WRITE"}

_SYSTEM = """You are a query preprocessor for a developer analytics platform.
The platform lets developers query ONLY their own data (commits, pull requests, code reviews, performance scores).

Your job: return a single JSON object with these fields:
{
  "reconstructed_q": "...",        // standalone, self-contained question (resolve pronouns from history)
  "intent": "...",                  // one of: DB_QUERY | INCOMPLETE | SENSITIVE | IRRELEVANT | CONVERSATIONAL | WRITE
  "reply": "...",                   // LLM-generated reply for non-DB_QUERY intents (null for DB_QUERY)
  "tables_hint": ["..."],           // for DB_QUERY: which tables likely needed (from: author, pr_reviewer, pr_comment, commit, hivelscore)
  "followup_question": "..."        // for INCOMPLETE: a specific clarifying question (null otherwise)
}

INTENT DEFINITIONS:
- DB_QUERY: requires fetching data from the database
- INCOMPLETE: question is about data but too vague to answer without clarification (ask once)
- SENSITIVE: asks for another user's data (name, email, commits — NOT the logged-in user)
- IRRELEVANT: completely off-topic (weather, jokes, general knowledge, news)
- CONVERSATIONAL: greetings, thanks, general chat, or questions about what you can help with
- WRITE: any intent to modify, delete, or update data

PRIORITY (if ambiguous): SENSITIVE > WRITE > INCOMPLETE > DB_QUERY > CONVERSATIONAL > IRRELEVANT

SCHEMA PRIVACY RULE: NEVER reveal actual table names, column names, or database structure in your reply.
When users ask what you can help with, describe in plain English: "I can show you your commits, pull request activity, code reviews, and performance scores."

REPLY GUIDELINES:
- CONVERSATIONAL: warm, friendly, natural. For schema questions describe capabilities in plain English.
- IRRELEVANT: politely decline, offer to help with their developer data.
- SENSITIVE/WRITE: politely explain you can only show the logged-in user's own data / that the system is read-only.
- INCOMPLETE: the reply field should be null; use followup_question instead.
- DB_QUERY: reply is null (answer comes from DB).

Respond ONLY with valid JSON. No markdown. No extra text."""


def reconstruct_and_classify(state: dict) -> dict:
    question = state.get("question", "")
    user_profile = state.get("user_profile", {})
    history = state.get("history", {})
    followup_count = state.get("followup_count", 0)

    logger.info("[Node02] Raw question: %r", question)

    # ── Build Haiku input ─────────────────────────────────────────────────────
    history_text = _format_history(history)

    user_msg = (
        f"logged_in_user: {json.dumps({'name': user_profile.get('name'), 'author_id': user_profile.get('author_id')})}\n"
        f"timezone: {user_profile.get('timezone', 'UTC')}\n"
        f"conversation_history:\n{history_text}\n\n"
        f"raw_question: {question}"
    )

    # ── Single Haiku call ─────────────────────────────────────────────────────
    try:
        response = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_msg}]
        )
        logger.info("[Node02] LLM response — fn=reconstruct_and_classify in=%d out=%d stop=%s text=%r",
                    response.usage.input_tokens, response.usage.output_tokens,
                    response.stop_reason, response.content[0].text[:120])
        raw_text = response.content[0].text.strip()
        # Strip markdown code fences if present
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text.strip())
        result = json.loads(raw_text)
    except (json.JSONDecodeError, IndexError, Exception) as exc:
        logger.error("[Node02] Haiku call failed: %s — falling back to DB_QUERY", exc)
        # Safe fallback: treat as DB_QUERY and let Node 06 handle it
        return {
            **state,
            "reconstructed_question": question,
            "intent": "DB_QUERY",
            "llm_reply": None,
            "followup_question": None,
            "tables_hint": [],
            "embedding": None,
        }

    intent = result.get("intent", "CONVERSATIONAL")
    reconstructed = result.get("reconstructed_q") or question
    llm_reply = result.get("reply")
    tables_hint = result.get("tables_hint") or []
    followup_question = result.get("followup_question")

    # ── INCOMPLETE counter logic ──────────────────────────────────────────────
    if intent == "INCOMPLETE":
        if followup_count >= MAX_FOLLOWUPS:
            # Override: Haiku generates a "please rephrase" message
            rephrase_reply = _generate_rephrase_message()
            logger.info("[Node02] INCOMPLETE limit reached — sending rephrase message")
            return {
                **state,
                "reconstructed_question": reconstructed,
                "intent": "CONVERSATIONAL",  # route as CONVERSATIONAL to send reply
                "llm_reply": rephrase_reply,
                "followup_question": None,
                "tables_hint": [],
                "embedding": None,
            }

    # ── Compute embedding for DB_QUERY (once, reused in Node 03+04) ──────────
    embedding = None
    if intent == "DB_QUERY":
        try:
            embedding = embed_question(reconstructed)
        except Exception as exc:
            logger.warning("[Node02] Embedding failed: %s — will recompute in cache node if needed", exc)

    logger.info("[Node02] Intent=%s | Reconstructed=%r | Tables hint=%s", intent, reconstructed, tables_hint)

    return {
        **state,
        "reconstructed_question": reconstructed,
        "intent": intent,
        "llm_reply": llm_reply,
        "followup_question": followup_question,
        "tables_hint": tables_hint,
        "embedding": embedding,
    }


def route_after_reconstruct(state: dict) -> str:
    intent = state.get("intent", "CONVERSATIONAL")
    if intent == "DB_QUERY":
        return "cache"
    if intent == "INCOMPLETE":
        return "followup"
    # CONVERSATIONAL, IRRELEVANT, SENSITIVE, WRITE → reject/reply node
    return "reject"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _generate_rephrase_message() -> str:
    """Haiku generates a polite 'please rephrase' when follow-up limit reached."""
    try:
        resp = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            messages=[{
                "role": "user",
                "content": (
                    "A user has asked the same unclear question 3 times. "
                    "Generate a single friendly sentence asking them to rephrase "
                    "or be more specific about what data they want to see."
                )
            }]
        )
        logger.info("[Node02] LLM response — fn=_generate_rephrase_message in=%d out=%d stop=%s text=%r",
                    resp.usage.input_tokens, resp.usage.output_tokens,
                    resp.stop_reason, resp.content[0].text[:120])
        return resp.content[0].text.strip()
    except Exception:
        return "Could you please rephrase your question with more specific details about what you'd like to see?"


def _format_history(history: dict) -> str:
    summary = history.get("summary", "")
    recent = history.get("recent", [])
    lines = []
    if summary:
        lines.append(f"[Summary of earlier conversation]: {summary}")
    for msg in recent:
        lines.append(f"{msg['role']}: {msg['content']}")
    return "\n".join(lines) if lines else "(no previous conversation)"
