"""
FastAPI app with WebSocket endpoint /ws/chat/{session_id}.
Handles: question → pipeline → streaming tokens back.
Supports: stop, edit (restarts from Node 1), optimistic reconstruction display.
"""
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

_NODE_STATUS: dict[str, str] = {
    "load_context":  "Loading conversation history...",
    "safety":        "Running safety check...",
    "reconstruct":   "Understanding your question...",
    "cache":         "Checking cache...",
    "check":         "Matching similar questions...",
    "sql":           "Querying the database...",
    "validate":      "Validating answer...",
}

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from graph import build_graph
from db import soft_delete_conversation, save_message, get_conversation_history
from scripts.generate_schema import generate_schema

_graph = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph
    generate_schema()          # Refresh db_schema.json at startup
    db_url = os.getenv("DATABASE_URL")
    async with AsyncPostgresSaver.from_conn_string(db_url) as checkpointer:
        await checkpointer.setup()
        _graph = build_graph(checkpointer=checkpointer)
        yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws/chat/{session_id}")
async def chat_ws(websocket: WebSocket, session_id: str):
    await websocket.accept()
    bg_task: asyncio.Task | None = None

    async def send(msg: dict):
        await websocket.send_text(json.dumps(msg))

    async def run_pipeline(question: str, user_profile: dict):
        config = {"configurable": {"thread_id": session_id}}

        # Save user message to conversation history
        save_message(session_id, role="user", content=question, raw_question=question)

        # Token streaming callback passed into state for Node 6
        async def token_callback(event: dict):
            await send(event)

        initial_state = {
            "session_id": session_id,
            "question": question,
            "user_profile": user_profile,
            "reconstructed_question": None,
            "history": None,
            "schema": None,
            "intent": None,
            "followup_count": 0,
            "cache_source": None,
            "candidates": None,
            "answer": None,
            "sql_generated": None,
            "validated": None,
            "threat": False,
            "rejection_reason": None,
            "validation_verdict": None,
            "token_callback": token_callback,
        }

        # Stream events from LangGraph
        async for event in _graph.astream_events(initial_state, config=config, version="v2"):
            etype = event.get("event")
            node = event.get("name", "")
            data = event.get("data", {})

            # Send status update when a node starts
            if etype == "on_chain_start" and node in _NODE_STATUS:
                logger.info("Node starting: %s", node)
                await send({"type": "status", "message": _NODE_STATUS[node]})

            # After reconstruct node — send reconstructed query to UI
            if etype == "on_chain_end" and node == "reconstruct":
                output = data.get("output", {})
                intent = output.get("intent")
                rejection = output.get("rejection_reason")
                reconstructed = output.get("reconstructed_question", question)

                if intent == "IRRELEVANT":
                    await send({"type": "token", "content": "Hi! I'm a database assistant. Ask me anything about the data — like counts, filters, or summaries."})
                    await send({"type": "done"})
                    return

                if intent in ("ANOMALY", "SENSITIVE", "WRITE", "INCOMPLETE_LIMIT"):
                    await send({"type": "rejected", "reason": rejection or f"Question classified as {intent}."})
                    return

                if intent == "INCOMPLETE":
                    await send({"type": "followup", "message": "Could you clarify your question?"})
                    return

                if intent == "META_SCHEMA":
                    pass  # answer will come through end event

                if intent == "DB_QUERY":
                    await send({
                        "type": "reconstructed_query",
                        "original": question,
                        "query": reconstructed,
                    })

            # After safety node — threat detected
            if etype == "on_chain_end" and node == "safety":
                output = data.get("output", {})
                if output.get("threat"):
                    await send({"type": "rejected", "reason": output.get("rejection_reason", "Request blocked.")})
                    return

            # Final answer (end of pipeline)
            if etype == "on_chain_end" and node in ("meta", "followup", "error"):
                output = data.get("output", {})
                answer = output.get("answer", "")
                if answer:
                    await send({"type": "token", "content": answer})

        logger.info("Pipeline complete for session %s", session_id)
        await send({"type": "done"})

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "question":
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
                # Treat edited query as a brand new question — restarts from Node 1
                if bg_task and not bg_task.done():
                    bg_task.cancel()
                bg_task = asyncio.create_task(
                    run_pipeline(msg["query"], msg.get("user_profile", {}))
                )

            elif msg_type == "delete_conversation":
                soft_delete_conversation(session_id)
                await send({"type": "done"})

    except WebSocketDisconnect:
        if bg_task and not bg_task.done():
            bg_task.cancel()


@app.get("/api/history/{session_id}")
async def get_history(session_id: str):
    recent_count = int(os.getenv("RECENT_HISTORY_COUNT", 5))
    return get_conversation_history(session_id, recent_count)


@app.get("/health")
async def health():
    return {"status": "ok"}
