"""
FastAPI app — WebSocket /ws/chat/{session_id} + REST /api/session.

WebSocket protocol:
  Client → Server: {type: "question", text: "...", user_profile: {...}}
  Client → Server: {type: "stop"}
  Client → Server: {type: "edit", query: "..."}
  Server → Client: {type: "reconstructed_query", original: "...", query: "..."}
  Server → Client: {type: "token", content: "..."}
  Server → Client: {type: "followup", message: "..."}
  Server → Client: {type: "rejected", reason: "..."}
  Server → Client: {type: "done"}
  Server → Client: {type: "error", message: "..."}
"""
import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from graph import build_graph
from db import soft_delete_conversation, save_message, get_conversation_history, get_or_create_conversation, get_all_messages
from scripts.generate_schema import generate_schema

_graph = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph

    # ── 1. Load schema from Source DB into memory ──────────────────────────────
    schema_ok = generate_schema()
    logger.info("Schema cache ready (live=%s)", schema_ok)

    # ── 2. Build LangGraph with App DB checkpointer ────────────────────────────
    app_db_url = os.getenv("APP_DB_URL")
    async with AsyncPostgresSaver.from_conn_string(app_db_url) as checkpointer:
        await checkpointer.setup()
        _graph = build_graph(checkpointer=checkpointer)
        logger.info("LangGraph pipeline ready")
        yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── REST: Session Creation ─────────────────────────────────────────────────────

class SessionRequest(BaseModel):
    author_id: int
    account_id: str
    organization_id: int
    name: str
    timezone: str
    team_id: int | None = None


@app.post("/api/session")
async def create_session(req: SessionRequest):
    """
    Create a new chat session tied to an author_id.
    Returns a session_id for the WebSocket connection.
    """
    session_id = str(uuid.uuid4())
    get_or_create_conversation(session_id, req.author_id)
    logger.info("New session created: %s for author_id=%s", session_id, req.author_id)
    return {"session_id": session_id}


# ── REST: History ──────────────────────────────────────────────────────────────

@app.get("/api/history/{session_id}")
async def get_history(session_id: str):
    recent_count = int(os.getenv("RECENT_HISTORY_COUNT", 5))
    return get_conversation_history(session_id, recent_count)


@app.get("/api/messages/{session_id}")
async def get_messages(session_id: str):
    """Returns all messages for a session (used by the UI to restore chat history)."""
    return {"messages": get_all_messages(session_id)}


# ── REST: Health ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    import schema_cache
    schema = schema_cache.get_schema()
    return {
        "status": "ok",
        "schema_tables": list(schema.keys()),
        "schema_version": schema_cache.get_version_hash()[:8],
    }


# ── WebSocket: Chat ────────────────────────────────────────────────────────────

@app.websocket("/ws/chat/{session_id}")
async def chat_ws(websocket: WebSocket, session_id: str):
    await websocket.accept()
    bg_task: asyncio.Task | None = None

    async def send(msg: dict):
        try:
            await websocket.send_text(json.dumps(msg))
        except Exception:
            pass

    async def run_pipeline(question: str, user_profile: dict):
        config = {"configurable": {"thread_id": session_id}}
        author_id = int(user_profile.get("author_id", 0))

        # Save user message to conversation history
        try:
            save_message(
                session_id=session_id,
                author_id=author_id,
                role="user",
                content=question,
                raw_question=question,
            )
        except Exception as exc:
            logger.error("Failed to save user message: %s", exc)

        # WebSocket streaming callback for Node 06 tokens
        async def token_callback(event: dict):
            await send(event)

        initial_state = {
            "session_id":           session_id,
            "question":             question,
            "user_profile":         user_profile,
            "reconstructed_question": None,
            "history":              None,
            "schema":               None,
            "intent":               None,
            "followup_count":       0,
            "cache_source":         None,
            "candidates":           None,
            "embedding":            None,
            "tables_hint":          [],
            "answer":               None,
            "sql_generated":        None,
            "validated":            None,
            "retry_count":          0,
            "threat":               False,
            "context_error":        None,
            "llm_reply":            None,
            "followup_question":    None,
            "validation_verdict":   None,
            "token_callback":       token_callback,
        }

        pipeline_complete = False

        _NODE_STATUS = {
            "safety":      "Running safety checks…",
            "reconstruct": "Classifying your question…",
            "cache":       "Checking semantic cache…",
            "check":       "Evaluating cached results…",
            "sql":         "Querying the database…",
            "validate":    "Validating answer…",
        }

        async for event in _graph.astream_events(initial_state, config=config, version="v2"):
            etype = event.get("event")
            node  = event.get("name", "")
            data  = event.get("data", {})

            if etype == "on_chain_start" and node in _NODE_STATUS:
                logger.info("[Pipeline] ▶ %s starting", node)
                await send({"type": "status", "message": _NODE_STATUS[node]})

            if etype == "on_chain_end" and node in _NODE_STATUS:
                logger.info("[Pipeline] ✓ %s done", node)

            # ── After safety node ────────────────────────────────────────────
            if etype == "on_chain_end" and node == "safety":
                output = data.get("output", {})
                if output.get("threat"):
                    reason = output.get("llm_reply") or "Your request could not be processed."
                    await send({"type": "rejected", "reason": reason})
                    return

            # ── After reconstruct node ───────────────────────────────────────
            if etype == "on_chain_end" and node == "reconstruct":
                output = data.get("output", {})
                intent             = output.get("intent")
                reconstructed      = output.get("reconstructed_question", question)
                llm_reply          = output.get("llm_reply")
                followup_question  = output.get("followup_question")

                if intent == "DB_QUERY":
                    # Optimistic send — show reconstructed question to user
                    await send({
                        "type":     "reconstructed_query",
                        "original": question,
                        "query":    reconstructed,
                    })

                elif intent == "INCOMPLETE":
                    msg = followup_question or llm_reply or "Could you clarify your question?"
                    await send({"type": "followup", "message": msg})
                    await send({"type": "done"})
                    return

                elif intent == "CONVERSATIONAL":
                    reply = llm_reply or "I'm here to help! Ask me about your commits, pull requests, or performance scores."
                    await send({"type": "token", "content": reply})
                    await send({"type": "done"})
                    return

                else:
                    # SENSITIVE / WRITE / IRRELEVANT
                    reason = llm_reply or "I can't help with that request."
                    await send({"type": "rejected", "reason": reason})
                    return

            # ── After validate node (done path) ──────────────────────────────
            if etype == "on_chain_end" and node == "validate":
                output = data.get("output", {})
                if output.get("validated"):
                    pipeline_complete = True
                    # Tokens were streamed by Node 06 callback; send done signal
                    await send({"type": "done"})
                    return

            # ── After error node ─────────────────────────────────────────────
            if etype == "on_chain_end" and node == "error":
                output = data.get("output", {})
                error_msg = (
                    output.get("llm_reply")
                    or "I wasn't able to find a reliable answer. Please try rephrasing."
                )
                await send({"type": "error", "message": error_msg})
                return

        if not pipeline_complete:
            logger.warning("Pipeline ended without completion for session %s", session_id)
            await send({"type": "done"})

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "question":
                # Cancel any running pipeline
                if bg_task and not bg_task.done():
                    bg_task.cancel()
                bg_task = asyncio.create_task(
                    run_pipeline(msg["text"], msg.get("user_profile", {}))
                )

            elif msg_type == "stop":
                if bg_task and not bg_task.done():
                    bg_task.cancel()
                await send({"type": "done"})

            elif msg_type == "edit":
                # User edited the reconstructed query — restart from Node 01
                if bg_task and not bg_task.done():
                    bg_task.cancel()
                bg_task = asyncio.create_task(
                    run_pipeline(msg["query"], msg.get("user_profile", {}))
                )

            elif msg_type == "delete_conversation":
                soft_delete_conversation(session_id)
                await send({"type": "done"})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: session %s", session_id)
        if bg_task and not bg_task.done():
            bg_task.cancel()
    except Exception as exc:
        logger.error("WebSocket error for session %s: %s", session_id, exc, exc_info=True)
        if bg_task and not bg_task.done():
            bg_task.cancel()
