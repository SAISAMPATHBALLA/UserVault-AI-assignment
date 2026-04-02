"""Node 1: Rule-based safety filter — SQL injection + prompt injection detection."""
import re
import logging

logger = logging.getLogger(__name__)

_SQL_INJECTION = re.compile(
    r"\b(DROP|DELETE|TRUNCATE|ALTER|INSERT|UPDATE|CREATE|GRANT|REVOKE|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)
_PROMPT_INJECTION = re.compile(
    r"(ignore\s+(all\s+)?(previous|prior|above)\s+instructions?|"
    r"you\s+are\s+now\s+|"
    r"disregard\s+|"
    r"forget\s+everything|"
    r"new\s+persona|"
    r"act\s+as\s+)",
    re.IGNORECASE,
)


def safety_filter(state: dict) -> dict:
    question = state.get("question", "")
    logger.info("[Safety] Checking: %r", question)

    if _SQL_INJECTION.search(question):
        logger.warning("[Safety] SQL injection detected in: %r", question)
        return {**state, "threat": True, "rejection_reason": "Potential SQL injection detected."}

    if _PROMPT_INJECTION.search(question):
        logger.warning("[Safety] Prompt injection detected in: %r", question)
        return {**state, "threat": True, "rejection_reason": "Potential prompt injection detected."}

    logger.info("[Safety] Passed")
    return {**state, "threat": False}


def is_threat(state: dict) -> str:
    return "reject" if state.get("threat") else "continue"
