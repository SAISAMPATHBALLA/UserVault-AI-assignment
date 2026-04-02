"""
PostgreSQL MCP Server — SSE transport via uvicorn.
Provides a `query_database` tool and `list_tables` tool against the Source DB (read-only).

The main pipeline (Node 06) uses direct psycopg2 execution for speed.
This MCP server is available for external tool integrations and future use.

Usage:
    python mcp_server.py
    # or via start.bat (started alongside main backend)
"""
import logging
import os
import re

import psycopg2
import uvicorn
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [MCP] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

SOURCE_DB_URL = os.getenv("SOURCE_DB_URL")
PORT = int(os.getenv("POSTGRES_MCP_PORT", 5433))

_WRITE_PATTERN = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|EXEC)\b",
    re.IGNORECASE,
)
_LIMIT_PATTERN = re.compile(r"\bLIMIT\s+\d+\b", re.IGNORECASE)

mcp = FastMCP(
    "postgres-source-db",
    instructions="Read-only PostgreSQL analytics database. Only SELECT queries permitted.",
)


@mcp.tool()
def query_database(sql: str) -> str:
    """
    Execute a read-only SELECT query against the analytics Source DB.

    Args:
        sql: A valid SQL SELECT statement. Write operations are rejected.

    Returns:
        Query results as a text table, or an error message.
    """
    logger.info("Tool call: query_database — %s", sql[:120])

    if not sql.strip():
        return "ERROR: Empty query."

    if _WRITE_PATTERN.match(sql.strip()):
        return "ERROR: Only SELECT queries are permitted. Write operations are blocked."

    # Code-level LIMIT enforcement
    if not _LIMIT_PATTERN.search(sql):
        sql = sql.rstrip().rstrip(";") + " LIMIT 100"

    try:
        conn = psycopg2.connect(SOURCE_DB_URL)
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cur:
            cur.execute(sql)
            if cur.description is None:
                conn.close()
                return "Query executed (no rows returned)."
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        conn.close()

        if not rows:
            return "No rows returned."

        lines = [" | ".join(cols), "-" * max(len(" | ".join(cols)), 10)]
        for row in rows:
            lines.append(" | ".join("NULL" if v is None else str(v) for v in row))
        lines.append(f"\n({len(rows)} row{'s' if len(rows) != 1 else ''} returned)")
        return "\n".join(lines)

    except psycopg2.Error as exc:
        return f"ERROR: {_sanitize_error(exc)}"
    except Exception as exc:
        logger.error("Unexpected MCP tool error: %s", exc)
        return "ERROR: Unexpected error."


@mcp.tool()
def list_tables() -> str:
    """List all available tables in the analytics Source DB."""
    try:
        conn = psycopg2.connect(SOURCE_DB_URL)
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' ORDER BY table_name
            """)
            tables = [r[0] for r in cur.fetchall()]
        conn.close()
        return "Available tables:\n" + "\n".join(f"  - {t}" for t in tables)
    except Exception as exc:
        return f"ERROR: {_sanitize_error(exc)}"


def _sanitize_error(exc) -> str:
    code_map = {
        "42P01": "Table not found.",
        "42703": "Column not found.",
        "22P02": "Invalid input value.",
        "42601": "SQL syntax error.",
        "57014": "Query cancelled — too slow.",
    }
    pgcode = getattr(exc, "pgcode", None)
    return code_map.get(pgcode, "Database error.")


if __name__ == "__main__":
    if not SOURCE_DB_URL:
        raise RuntimeError("SOURCE_DB_URL not set in .env")
    host_part = SOURCE_DB_URL.split("@")[-1] if "@" in SOURCE_DB_URL else "configured"
    logger.info("MCP Server starting on port %d → Source DB: %s", PORT, host_part)
    app = mcp.sse_app()
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
