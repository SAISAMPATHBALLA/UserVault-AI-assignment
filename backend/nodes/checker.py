"""
Node 05: Question Checker (Haiku).
1. Time-sensitive detection FIRST — if yes, return NONE immediately (force fresh SQL)
2. Semantic match check on top-5 pgvector candidates
   Handles: negations, entity swaps, temporal differences, superlatives
"""
import logging
import os
import re

import anthropic

logger = logging.getLogger(__name__)
_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Temporal keywords that make a question time-sensitive → always fetch fresh data
_TEMPORAL_PATTERN = re.compile(
    r"\b(yesterday|today|tonight|this week|last week|this month|last month|"
    r"this year|last year|recent|recently|just|latest|current|now|"
    r"past \d+ days?|past \d+ weeks?|past \d+ months?)\b",
    re.IGNORECASE,
)

_MATCH_SYSTEM = """You are a semantic question matcher for a developer analytics chatbot.

Given a user's question and up to 5 cached questions, determine which cached question
(if any) is asking for EXACTLY the same data.

These are NON-MATCHES even at high similarity:
- Negations: "commits FROM main" vs "commits NOT FROM main"
- Different entities/values: "PR count this sprint" vs "PR count last sprint"
- Opposite superlatives: "OLDEST commit" vs "MOST RECENT commit"
- Different aggregations: "COUNT of PRs" vs "LIST of PRs"
- Different users mentioned (should not occur, but check)

Reply ONLY with a single number (1-5) for the matching question index, or NONE.
No explanation. Just the number or NONE."""


def check_candidates(state: dict) -> dict:
    candidates = state.get("candidates", [])
    if not candidates:
        return {**state, "answer": None, "cache_source": None}

    question = state["reconstructed_question"]
    user_timezone = state.get("user_profile", {}).get("timezone", "UTC")

    # ── 1. Time-sensitive detection → bypass cache ────────────────────────────
    if _TEMPORAL_PATTERN.search(question):
        logger.info("[Node05] Time-sensitive question detected — bypassing cache, forcing fresh SQL")
        return {**state, "answer": None, "cache_source": None}

    # ── 2. Haiku semantic match ───────────────────────────────────────────────
    numbered = "\n".join(f"{i+1}. {c['question']}" for i, c in enumerate(candidates))
    user_content = (
        f"User's current question: {question}\n"
        f"User timezone: {user_timezone}\n\n"
        f"Cached questions:\n{numbered}"
    )

    try:
        response = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            system=_MATCH_SYSTEM,
            messages=[{"role": "user", "content": user_content}]
        )
        logger.info("[Node05] LLM response — fn=check_candidates in=%d out=%d stop=%s text=%r",
                    response.usage.input_tokens, response.usage.output_tokens,
                    response.stop_reason, response.content[0].text[:120])
        result = response.content[0].text.strip()
    except Exception as exc:
        logger.error("[Node05] Haiku call failed: %s — routing to SQL agent", exc)
        return {**state, "answer": None, "cache_source": None}

    if result.upper() == "NONE":
        logger.info("[Node05] No semantic match — routing to SQL agent")
        return {**state, "answer": None, "cache_source": None}

    try:
        idx = int(result) - 1
        if 0 <= idx < len(candidates):
            matched = candidates[idx]
            logger.info("[Node05] Cache match: candidate %d (similarity=%.3f)", idx + 1, matched.get("similarity", 0))

            # Atomically increment hit_count
            _increment_hit_count(matched["id"])

            return {
                **state,
                "answer": matched["answer"],
                "sql_generated": matched.get("sql_generated"),
                "cache_source": "pgvector",
            }
    except (ValueError, TypeError):
        pass

    logger.info("[Node05] Could not parse match result '%s' — routing to SQL agent", result)
    return {**state, "answer": None, "cache_source": None}


def route_after_checker(state: dict) -> str:
    return "validate" if state.get("answer") else "sql"


def _increment_hit_count(log_id: int):
    """Atomically increment hit_count — no TOCTOU race condition."""
    try:
        from db import SessionLocal
        from sqlalchemy import text
        with SessionLocal() as db:
            db.execute(
                text("UPDATE question_logs SET hit_count = hit_count + 1 WHERE id = :id"),
                {"id": log_id}
            )
            db.commit()
    except Exception as exc:
        logger.warning("[Node05] Failed to increment hit_count: %s", exc)
