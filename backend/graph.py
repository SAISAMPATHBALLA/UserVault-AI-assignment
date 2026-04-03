"""
LangGraph pipeline definition.
Nodes: 00-Context → 01-Safety → 02-Reconstruct → 03/04-Cache → 05-Checker → 06-SQL → 07-Validate

State flow:
  DB_QUERY   → cache → check → sql → validate → done/retry/error
  INCOMPLETE → followup (END)
  Others     → reject  (END)
"""
import os
from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph

from nodes.context_loader import load_context
from nodes.safety import safety_filter, is_threat
from nodes.reconstructor import reconstruct_and_classify, route_after_reconstruct
from nodes.cache import cache_lookup, route_after_cache
from nodes.checker import check_candidates, route_after_checker
from nodes.validator import validate_answer, route_after_validation


class ChatState(TypedDict):
    # Core
    session_id: str
    question: str
    user_profile: dict

    # Pipeline outputs
    reconstructed_question: Optional[str]
    history: Optional[dict]
    schema: Optional[dict]
    intent: Optional[str]
    followup_count: int

    # Cache
    cache_source: Optional[str]
    candidates: Optional[list]
    embedding: Optional[list]           # Pre-computed in Node 02, reused in Node 03+04
    tables_hint: Optional[list]         # Table hint from Node 02 for Node 06 acceleration

    # Answer
    answer: Optional[str]
    sql_generated: Optional[str]
    validated: Optional[bool]
    retry_count: int                    # Node 07 → Node 06 retry counter (max 2)

    # Error / rejection paths
    threat: bool
    context_error: Optional[str]       # From Node 00 validation failure
    llm_reply: Optional[str]           # LLM-generated reply for non-DB paths
    followup_question: Optional[str]   # Clarifying question for INCOMPLETE intent
    validation_verdict: Optional[str]

    # WebSocket streaming callback (async callable)
    token_callback: Optional[object]


# ── Async → sync wrappers for LangGraph ───────────────────────────────────────

def _wrap_cache_node(state: ChatState) -> ChatState:
    import asyncio
    return asyncio.run(cache_lookup(state))


def _wrap_validate_node(state: ChatState) -> ChatState:
    import asyncio
    return asyncio.run(validate_answer(state))


def _wrap_sql_node(state: ChatState) -> ChatState:
    import asyncio
    from nodes.sql_agent import run_sql_agent
    callback = state.get("token_callback")
    return asyncio.run(run_sql_agent(state, callback))


# ── Terminal nodes (pass-through — main.py reads state and sends WS messages) ─

def _reject_node(state: ChatState) -> ChatState:
    """Terminal node for CONVERSATIONAL / IRRELEVANT / SENSITIVE / WRITE intents."""
    return state


def _followup_node(state: ChatState) -> ChatState:
    """Terminal node for INCOMPLETE intent — followup_question already in state."""
    return state


def _error_node(state: ChatState) -> ChatState:
    """Terminal node for unrecoverable validation failure — llm_reply already in state."""
    return state


# ── Graph assembly ─────────────────────────────────────────────────────────────

def build_graph(checkpointer=None):
    g = StateGraph(ChatState)

    # Register nodes
    g.add_node("load_context",  load_context)
    g.add_node("safety",        safety_filter)
    g.add_node("reconstruct",   reconstruct_and_classify)
    g.add_node("cache",         _wrap_cache_node)
    g.add_node("check",         check_candidates)
    g.add_node("sql",           _wrap_sql_node)
    g.add_node("validate",      _wrap_validate_node)
    g.add_node("reject",        _reject_node)
    g.add_node("followup",      _followup_node)
    g.add_node("error",         _error_node)

    # Entry point
    g.set_entry_point("load_context")

    # Fixed edges
    g.add_edge("load_context", "safety")

    # Safety → reconstruct or reject (threat)
    g.add_conditional_edges("safety", is_threat, {
        "reject":   "reject",
        "continue": "reconstruct",
    })

    # Reconstruct → cache (DB_QUERY) | followup (INCOMPLETE) | reject (all others)
    g.add_conditional_edges("reconstruct", route_after_reconstruct, {
        "cache":    "cache",
        "followup": "followup",
        "reject":   "reject",
    })

    # Cache → validate (redis hit) | check (pgvector candidates) | sql (miss)
    g.add_conditional_edges("cache", route_after_cache, {
        "validate": "validate",
        "check":    "check",
        "sql":      "sql",
    })

    # Checker → validate (match) | sql (no match / time-sensitive)
    g.add_conditional_edges("check", route_after_checker, {
        "validate": "validate",
        "sql":      "sql",
    })

    # SQL always goes to validate
    g.add_edge("sql", "validate")

    # Validate → done | sql (retry) | error (exhausted retries or threat)
    g.add_conditional_edges("validate", route_after_validation, {
        "done":  END,
        "sql":   "sql",
        "error": "error",
    })

    # Terminal nodes
    g.add_edge("reject",   END)
    g.add_edge("followup", END)
    g.add_edge("error",    END)

    return g.compile(checkpointer=checkpointer)
