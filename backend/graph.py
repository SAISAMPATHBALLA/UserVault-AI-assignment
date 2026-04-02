"""
LangGraph pipeline definition.
Nodes: 0-Load → 1-Safety → 2-Reconstruct → 3/4-Cache → 5-Checker → 6-SQL → 7-Validate
"""
import os
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from typing import TypedDict, Optional

from nodes.context_loader import load_context
from nodes.safety import safety_filter, is_threat
from nodes.reconstructor import reconstruct_and_classify, route_after_reconstruct
from nodes.cache import cache_lookup, route_after_cache
from nodes.checker import check_candidates, route_after_checker
from nodes.validator import validate_answer, route_after_validation


class ChatState(TypedDict):
    session_id: str
    question: str
    user_profile: dict
    reconstructed_question: Optional[str]
    history: Optional[dict]
    schema: Optional[dict]
    intent: Optional[str]
    followup_count: int
    cache_source: Optional[str]
    candidates: Optional[list]
    answer: Optional[str]
    sql_generated: Optional[str]
    validated: Optional[bool]
    threat: bool
    rejection_reason: Optional[str]
    validation_verdict: Optional[str]
    token_callback: Optional[object]  # async callable for WebSocket streaming


def _wrap_sql_node(state: ChatState) -> ChatState:
    """Wraps async sql agent for sync LangGraph node."""
    import asyncio
    from nodes.sql_agent import run_sql_agent
    callback = state.get("token_callback")
    return asyncio.get_event_loop().run_until_complete(run_sql_agent(state, callback))


def _wrap_cache_node(state: ChatState) -> ChatState:
    import asyncio
    from nodes.cache import cache_lookup
    return asyncio.get_event_loop().run_until_complete(cache_lookup(state))


def _wrap_validate_node(state: ChatState) -> ChatState:
    import asyncio
    return asyncio.get_event_loop().run_until_complete(validate_answer(state))


def _reject_node(state: ChatState) -> ChatState:
    return state


def _meta_schema_node(state: ChatState) -> ChatState:
    schema = state.get("schema", {})
    tables = schema.get("tables", {})
    if not tables:
        answer = "No schema information available."
    else:
        lines = []
        for tname, tinfo in tables.items():
            cols = list(tinfo.get("columns", {}).keys())
            lines.append(f"Table '{tname}': {', '.join(cols)}")
        answer = "Available data:\n" + "\n".join(lines)
    return {**state, "answer": answer, "validated": True}


def _followup_node(state: ChatState) -> ChatState:
    return {
        **state,
        "answer": "Could you clarify your question? What specific information are you looking for?",
        "validated": True,
    }


def _error_node(state: ChatState) -> ChatState:
    return {
        **state,
        "answer": "I couldn't find reliable information for that question. Please try rephrasing.",
        "validated": False,
    }


def build_graph(checkpointer=None) -> StateGraph:
    g = StateGraph(ChatState)

    g.add_node("load_context", load_context)
    g.add_node("safety", safety_filter)
    g.add_node("reconstruct", reconstruct_and_classify)
    g.add_node("cache", _wrap_cache_node)
    g.add_node("check", check_candidates)
    g.add_node("sql", _wrap_sql_node)
    g.add_node("validate", _wrap_validate_node)
    g.add_node("reject", _reject_node)
    g.add_node("meta", _meta_schema_node)
    g.add_node("followup", _followup_node)
    g.add_node("error", _error_node)

    g.set_entry_point("load_context")
    g.add_edge("load_context", "safety")
    g.add_conditional_edges("safety", is_threat, {"reject": "reject", "continue": "reconstruct"})
    g.add_conditional_edges("reconstruct", route_after_reconstruct, {
        "cache": "cache",
        "meta": "meta",
        "followup": "followup",
        "reject": "reject",
    })
    g.add_conditional_edges("cache", route_after_cache, {
        "validate": "validate",
        "check": "check",
        "sql": "sql",
    })
    g.add_conditional_edges("check", route_after_checker, {
        "validate": "validate",
        "sql": "sql",
    })
    g.add_edge("sql", "validate")
    g.add_conditional_edges("validate", route_after_validation, {
        "done": END,
        "sql": "sql",
        "error": "error",
    })
    g.add_edge("reject", END)
    g.add_edge("meta", END)
    g.add_edge("followup", END)
    g.add_edge("error", END)

    return g.compile(checkpointer=checkpointer)


def create_graph_with_checkpointer():
    db_url = os.getenv("DATABASE_URL")
    checkpointer = PostgresSaver.from_conn_string(db_url)
    return build_graph(checkpointer=checkpointer)
