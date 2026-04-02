"""
Node 6: Live SQL Agent (embedded agent).
Claude Haiku + PostgreSQL MCP server. Haiku dynamically decides which MCP tools to call.
Restricted to SELECT queries only via system prompt.
Streams tokens back via WebSocket callback.
"""
import os
import json
import anthropic

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MCP_URL = f"http://localhost:{os.getenv('POSTGRES_MCP_PORT', 5433)}"

_SYSTEM = """You are a read-only database assistant. You help users query data.

RULES (non-negotiable):
- You may ONLY generate and execute SELECT queries.
- NEVER generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, or GRANT statements.
- If the question asks you to modify data, refuse and explain this is a read-only system.
- Answer only based on data returned from the database tools.
- Do not invent, assume, or hallucinate data.
- If tools return no results, say so clearly.

Use the available database tools to answer the question. Start by listing/describing relevant
tables if you are unsure of the schema, then query as needed.
"""


async def run_sql_agent(state: dict, token_callback=None) -> dict:
    question = state["reconstructed_question"]
    schema = state.get("schema", {})
    schema_hint = _build_schema_hint(schema)

    user_msg = f"Schema hint:\n{schema_hint}\n\nQuestion: {question}"

    # Agentic loop: Haiku calls MCP tools until it produces a final answer
    messages = [{"role": "user", "content": user_msg}]
    sql_used = []
    final_answer = ""

    mcp_server = anthropic.MCPServerHTTP(url=MCP_URL)

    async with _client.messages.stream(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=_SYSTEM,
        messages=messages,
        mcp_servers=[mcp_server],
    ) as stream:
        async for event in stream:
            if hasattr(event, "type"):
                if event.type == "content_block_delta" and hasattr(event.delta, "text"):
                    token = event.delta.text
                    final_answer += token
                    if token_callback:
                        await token_callback({"type": "token", "content": token})

                elif event.type == "content_block_start":
                    if hasattr(event.content_block, "type") and event.content_block.type == "tool_use":
                        tool_input = getattr(event.content_block, "input", {})
                        if "query" in tool_input:
                            sql_used.append(tool_input["query"])

    return {
        **state,
        "answer": final_answer.strip(),
        "sql_generated": "; ".join(sql_used) if sql_used else None,
        "cache_source": "llm",
    }


def _build_schema_hint(schema: dict) -> str:
    if not schema:
        return "Use list_tables and describe_table tools to discover the schema."
    tables = schema.get("tables", {})
    lines = []
    for tname, tinfo in tables.items():
        cols = tinfo.get("columns", {})
        col_str = ", ".join(
            f"{c}({v.get('type','?')})" + (" PK" if v.get("primary_key") else "")
            for c, v in cols.items()
        )
        lines.append(f"  {tname}: {col_str}")
    return "\n".join(lines) if lines else "Schema not loaded."
