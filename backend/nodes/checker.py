"""
Node 5: Question Checker (Haiku).
Receives top-5 pgvector candidates, picks the best match or returns NONE.
Handles negations, entity swaps, temporal differences, superlatives.
"""
import os
import anthropic

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

_SYSTEM = """You are a semantic question matcher.

Given a user's question and up to 5 cached questions, determine which cached question
(if any) asks for EXACTLY the same database information.

Consider these as NON-MATCHES even at high similarity:
- Negations: "users FROM Mumbai" vs "users NOT FROM Mumbai"
- Different entities: "users from Mumbai" vs "users from Delhi"
- Temporal differences: "registered THIS WEEK" vs "registered LAST WEEK"
- Opposite superlatives: "OLDEST user" vs "YOUNGEST user"
- Different aggregations: "COUNT of users" vs "LIST of users"

Reply with ONLY a single number (1-5) for the matching question, or NONE if no match.
No explanation. Just the number or NONE.
"""


def check_candidates(state: dict) -> dict:
    candidates = state.get("candidates", [])
    if not candidates:
        return {**state, "answer": None}

    question = state["reconstructed_question"]
    numbered = "\n".join(f"{i+1}. {c['question']}" for i, c in enumerate(candidates))

    response = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        system=_SYSTEM,
        messages=[{"role": "user", "content": f"User question: {question}\n\nCached questions:\n{numbered}"}]
    )

    result = response.content[0].text.strip()

    if result == "NONE":
        return {**state, "answer": None, "cache_source": None}

    try:
        idx = int(result) - 1
        if 0 <= idx < len(candidates):
            matched = candidates[idx]
            return {
                **state,
                "answer": matched["answer"],
                "cache_source": "pgvector",
            }
    except ValueError:
        pass

    return {**state, "answer": None, "cache_source": None}


def route_after_checker(state: dict) -> str:
    return "validate" if state.get("answer") else "sql"
