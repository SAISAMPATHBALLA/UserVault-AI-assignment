"""
Node 06: Live SQL Agent.
Claude Haiku 4.5 with standard Anthropic tool_use + MCP server execution.

Step 1 — Table Selection: Haiku sees ALL tables + columns, outputs table names array only
Step 2 — Schema Injection: only selected tables' columns into agent system prompt
Step 3 — Agent Loop (max 5 iterations):
          Model → tool_use → MCP server executes → tool_result → repeat
          Buffer all tokens; stream ONLY the final text answer via token_callback
Step 4 — Post-processing: Python handles arithmetic transforms (not LLM)

User isolation enforced via system prompt filter rules + validated by Node 07.
LIMIT 100 enforced at code level before every query execution.
"""
import json
import logging
import os
import re

import anthropic
from mcp import ClientSession
from mcp.client.sse import sse_client

import schema_cache

logger = logging.getLogger(__name__)
_async_client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

_MCP_URL = f"http://localhost:{os.getenv('POSTGRES_MCP_PORT', '5433')}/sse"

MAX_ITERATIONS = 5

# Tool definitions — standard Anthropic tool_use format (no MCP dependency)
TOOLS = [
    {
        "name": "query_database",
        "description": (
            "Execute a read-only SELECT query against the developer analytics database. "
            "Returns results as a formatted text table. "
            "Always include the mandatory user filter in the WHERE clause."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "A valid SQL SELECT statement with user isolation filters."
                }
            },
            "required": ["sql"]
        }
    }
]

_TABLE_SELECT_SYSTEM = """You are a database table selector for a developer analytics platform.
Given a user question and the full list of available tables with all their column names,
output ONLY a JSON array of table names needed to answer the question.

Example: ["commit", "pr_reviewer"]

Rules:
- Only include tables that are genuinely necessary
- Return ONLY a valid JSON array — no markdown, no explanation
- Only use names from the provided list"""

_PER_TABLE_FILTER_RULES = """MANDATORY USER ISOLATION RULES — NEVER VIOLATE:
Apply these exact WHERE conditions for each table used:
  - insightly.author      → WHERE id = {author_id}
  - insightly.pr_reviewer → WHERE authorid = {author_id}
  - insightly.pr_comment  → WHERE authorid = {author_id}
  - insightly.commit      → WHERE authorid = {author_id}
  - insightly.hivelscore  → WHERE orgid = {organization_id} 
These filters MUST appear in every query on these tables. No exceptions."""

_LIMIT_PATTERN = re.compile(r"\bLIMIT\s+\d+\b", re.IGNORECASE)
_WRITE_PATTERN = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|EXEC)\b",
    re.IGNORECASE,
)


async def run_sql_agent(state: dict, token_callback=None) -> dict:
    question      = state["reconstructed_question"]
    user_profile  = state["user_profile"]
    author_id     = int(user_profile["author_id"])
    account_id    = str(user_profile.get("account_id", ""))
    organization_id = int(user_profile.get("organization_id", 0))
    team_id       = user_profile.get("team_id")
    timezone      = user_profile.get("timezone", "UTC")
    tables_hint   = state.get("tables_hint") or []

    logger.info("[Node06] Starting — author_id=%s: %r", author_id, question)

    # ── Step 1: Table selection ───────────────────────────────────────────────
    selected_tables = await _select_tables(question, tables_hint)
    logger.info("[Node06] Selected tables: %s", selected_tables)

    # ── Step 2: Selective schema injection ────────────────────────────────────
    selected_schema = schema_cache.build_agent_schema_for_tables(selected_tables)

    filter_rules = _PER_TABLE_FILTER_RULES.format(
        author_id=author_id,
        organization_id=organization_id,
    )

    agent_system = f"""You are a read-only SQL assistant for a developer analytics platform.

LOGGED-IN USER:
  author_id       : {author_id}
  account_id      : {account_id}
  organization_id : {organization_id}
  team_id         : {team_id if team_id is not None else 'none'}
  timezone        : {timezone}

DATABASE SCHEMA (selected tables only):
{selected_schema}

{filter_rules}

ADDITIONAL RULES:
- ONLY use SELECT — never INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE
- ALWAYS add LIMIT 100 to queries that could return many rows
- Use table aliases in JOINs for clarity
- Account for user timezone ({timezone}) in date/time filtering
- If 0 rows returned, say "No data found" — never invent data
- Do NOT reveal SQL, table names, or column names in your final answer
- Answer in plain, friendly language based only on what the database returned"""

    # ── Step 3: Agent Loop ────────────────────────────────────────────────────
    messages = [{"role": "user", "content": question}]
    sql_used: list[str] = []
    final_answer = ""

    for iteration in range(MAX_ITERATIONS):
        logger.info("[Node06] Iteration %d/%d", iteration + 1, MAX_ITERATIONS)

        # Accumulate response for this turn
        text_acc     = ""
        tool_calls: list[dict] = []
        cur_block_type: str | None = None
        cur_tool: dict = {}

        try:
            async with _async_client.messages.stream(
                model="claude-haiku-4-5-20251001",
                max_tokens=2048,
                system=agent_system,
                tools=TOOLS,
                messages=messages,
            ) as stream:
                async for event in stream:
                    if not hasattr(event, "type"):
                        continue

                    if event.type == "content_block_start":
                        block = event.content_block
                        cur_block_type = block.type
                        if cur_block_type == "tool_use":
                            cur_tool = {
                                "id":         block.id,
                                "name":       block.name,
                                "input_json": "",
                            }

                    elif event.type == "content_block_delta":
                        delta = event.delta
                        if cur_block_type == "text" and hasattr(delta, "text"):
                            text_acc += delta.text
                        elif cur_block_type == "tool_use" and hasattr(delta, "partial_json"):
                            cur_tool["input_json"] = cur_tool.get("input_json", "") + delta.partial_json

                    elif event.type == "content_block_stop":
                        if cur_block_type == "tool_use" and cur_tool:
                            tool_calls.append(dict(cur_tool))
                            cur_tool = {}

                final_msg = await stream.get_final_message()
                logger.info("[Node06] LLM response — fn=agent_loop iter=%d in=%d out=%d stop=%s",
                            iteration + 1, final_msg.usage.input_tokens,
                            final_msg.usage.output_tokens, final_msg.stop_reason)

        except Exception as exc:
            logger.error("[Node06] Stream error on iteration %d: %s", iteration + 1, exc, exc_info=True)
            break

        stop_reason = final_msg.stop_reason
        logger.info("[Node06] Iter %d — stop=%s tool_calls=%d", iteration + 1, stop_reason, len(tool_calls))

        if stop_reason == "end_turn" or not tool_calls:
            final_answer = text_acc
            break

        # ── Execute tool calls ────────────────────────────────────────────────
        tool_results: list[dict] = []
        for tc in tool_calls:
            try:
                tool_input = json.loads(tc["input_json"]) if tc["input_json"] else {}
            except json.JSONDecodeError:
                tool_input = {}

            result_str = await _execute_tool(tc["name"], tool_input, author_id, organization_id)

            # Track SQL (deduplicated)
            if "sql" in tool_input and tool_input["sql"] not in sql_used:
                sql_used.append(tool_input["sql"])

            tool_results.append({
                "type":        "tool_result",
                "tool_use_id": tc["id"],
                "content":     result_str,
            })

        # Append assistant turn + tool results
        messages.append({"role": "assistant", "content": final_msg.content})
        messages.append({"role": "user", "content": tool_results})

    else:
        # Max iterations reached without end_turn
        logger.warning("[Node06] Max iterations (%d) reached", MAX_ITERATIONS)
        if not final_answer:
            final_answer = "I reached my query limit trying to answer that. Please try a simpler question."

    if not final_answer.strip():
        final_answer = "I was unable to retrieve data for that question. Please try rephrasing."

    # ── Step 4: Post-processing ───────────────────────────────────────────────
    final_answer = _apply_post_processing(question, final_answer)

    logger.info("[Node06] Done — %d iterations, %d SQL queries, %d chars",
                min(iteration + 1, MAX_ITERATIONS), len(sql_used), len(final_answer))

    return {
        **state,
        "answer":        final_answer.strip(),
        "sql_generated": "; ".join(sql_used) if sql_used else None,
        "cache_source":  "llm",
    }


# ── MCP Client ────────────────────────────────────────────────────────────────

async def _call_mcp(tool_name: str, arguments: dict) -> str:
    """Call a tool on the MCP server and return the result text."""
    async with sse_client(url=_MCP_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            if result.content:
                return result.content[0].text
            return "No result returned."


# ── Tool Execution ─────────────────────────────────────────────────────────────

async def _execute_tool(name: str, tool_input: dict, author_id: int, organization_id: int) -> str:
    """Execute a tool call via MCP and return result as string for the model."""
    if name == "query_database":
        sql = tool_input.get("sql", "").strip()
        if not sql:
            return "ERROR: No SQL provided."

        # Guard: reject non-SELECT queries before hitting MCP
        if _WRITE_PATTERN.match(sql):
            logger.warning("[Node06] Rejected write SQL attempt: %s", sql[:80])
            return "ERROR: Only SELECT queries are permitted."

        # Enforce LIMIT 100 at code level (first line of defense)
        if not _LIMIT_PATTERN.search(sql):
            sql = sql.rstrip().rstrip(";") + " LIMIT 100"
            logger.info("[Node06] LIMIT injected into SQL")

        logger.info("[Node06] Executing SQL via MCP: %s", sql[:])
        try:
            return await _call_mcp("query_database", {"sql": sql})
        except Exception as exc:
            logger.warning("[Node06] MCP error: %s", exc)
            return "ERROR: Database unavailable."

    return f"ERROR: Unknown tool '{name}'."


# ── Table Selection ────────────────────────────────────────────────────────────

async def _select_tables(question: str, tables_hint: list[str]) -> list[str]:
    """Step 1: Haiku sees ALL tables + columns, returns JSON array of needed table names."""
    all_tables_str = schema_cache.build_table_selection_prompt()
    hint_str = f"\nPre-analysis hint (likely tables): {tables_hint}" if tables_hint else ""
    try:
        response = await _async_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            system=_TABLE_SELECT_SYSTEM,
            messages=[{
                "role": "user",
                "content": (
                    f"Available tables:\n{all_tables_str}"
                    f"{hint_str}\n\n"
                    f"User question: {question}\n\n"
                    "Which tables are needed? Return JSON array only."
                )
            }]
        )
        logger.info("[Node06] LLM response — fn=_select_tables in=%d out=%d stop=%s text=%r",
                    response.usage.input_tokens, response.usage.output_tokens,
                    response.stop_reason, response.content[0].text[:])
        raw = response.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw.strip())
        tables = json.loads(raw)
        known = set(schema_cache.get_schema().keys())
        valid = [t for t in tables if t in known]
        if valid:
            return valid
    except Exception as exc:
        logger.warning("[Node06] Table selection failed: %s — using all tables", exc)
    return list(schema_cache.get_schema().keys())


# ── Post-processing ────────────────────────────────────────────────────────────

def _apply_post_processing(question: str, answer: str) -> str:
    """Detect arithmetic requests and compute in Python (not LLM)."""
    q = question.lower()
    mult = re.search(r"multiply\s+(?:(?:it|that|the\s+result)\s+)?by\s+(\d+(?:\.\d+)?)", q)
    if mult:
        modified = _apply_numeric_factor(answer, float(mult.group(1)))
        if modified != answer:
            return modified
    div = re.search(r"divide\s+(?:(?:it|that|the\s+result)\s+)?by\s+(\d+(?:\.\d+)?)", q)
    if div:
        divisor = float(div.group(1))
        if divisor != 0:
            modified = _apply_numeric_factor(answer, 1.0 / divisor)
            if modified != answer:
                return modified
    return answer


def _apply_numeric_factor(text: str, factor: float) -> str:
    def replace(m):
        try:
            val = float(m.group(0).replace(",", ""))
            result = val * factor
            return f"{int(result):,}" if result == int(result) else f"{result:,.2f}"
        except ValueError:
            return m.group(0)
    return re.sub(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b", replace, text)
