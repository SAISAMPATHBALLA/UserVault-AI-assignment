"""
Source DB connection — AWS RDS PostgreSQL (read-only).
Uses psycopg2 ThreadedConnectionPool. SELECT only — enforced at DB user level.
Used by: generate_schema.py, schema_cache.py
"""
import logging
import os

import psycopg2
from psycopg2.pool import ThreadedConnectionPool

logger = logging.getLogger(__name__)

_pool: ThreadedConnectionPool | None = None


def _get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        dsn = os.getenv("SOURCE_DB_URL")
        if not dsn:
            raise RuntimeError("SOURCE_DB_URL not set in environment")
        _pool = ThreadedConnectionPool(minconn=1, maxconn=10, dsn=dsn)
        logger.info("[db_source] Connection pool created (Source DB)")
    return _pool


def execute_query(sql: str, params=None) -> list[dict]:
    """
    Execute a SELECT query on the Source DB and return rows as list of dicts.
    Caller must ensure SQL is SELECT-only — this is enforced by DB user permissions.
    """
    pool = _get_pool()
    conn = pool.getconn()
    try:
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description is None:
                return []
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            return [dict(zip(cols, row)) for row in rows]
    except psycopg2.Error as exc:
        # Sanitize error before propagating — strip schema/constraint details
        sanitized = _sanitize_pg_error(exc)
        raise RuntimeError(sanitized) from None
    finally:
        pool.putconn(conn)


def _sanitize_pg_error(exc: psycopg2.Error) -> str:
    """Strip PostgreSQL error details (schema, constraint names) before returning to caller."""
    pgcode = getattr(exc, "pgcode", None)
    error_map = {
        "42P01": "Table not found.",
        "42703": "Column not found.",
        "22P02": "Invalid input syntax.",
        "42601": "SQL syntax error.",
        "57014": "Query cancelled (timeout).",
    }
    if pgcode and pgcode in error_map:
        return error_map[pgcode]
    return "Database error. Please try rephrasing your question."


def close_pool():
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None
        logger.info("[db_source] Connection pool closed")
