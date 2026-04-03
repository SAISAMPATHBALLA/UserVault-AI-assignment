"""
In-memory schema cache for the 5 Source DB tables.
Loaded once at startup from AWS RDS. Never re-read per request.
Falls back to hardcoded known columns if DB unavailable.
"""
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

# ── Known schema (fallback if Source DB unavailable at startup) ────────────────
FALLBACK_SCHEMA: dict = {
    "author": {
        "description": "developer profiles and identity records",
        "columns": [
            "name", "email", "id", "nickname", "username", "profile", "avatar",
            "assignedauthorid", "type", "accountid", "scmprovider", "createddate",
            "modifieddate", "active", "organizationid", "joiningdate", "jobtitle",
            "onboardingtime", "skill", "manageremail", "grouphead", "vendor",
            "codingcategory", "firstactivitydate", "access_status", "archived",
            "generated", "sharedteams", "userintegrationid", "jira_author_id",
            "external", "labels",
        ],
        "user_filter": "WHERE id = {author_id}",
    },
    "pr_reviewer": {
        "description": "pull request review participation records",
        "columns": [
            "id", "pullrequestid", "authorid", "approved", "usertype", "comment",
            "accountid", "approveddate", "originalauthorid", "createddate",
            "modifieddate", "organizationid", "userintegrationid", "repoid",
        ],
        "user_filter": "WHERE authorid = {author_id}",
    },
    "pr_comment": {
        "description": "comments made on pull requests",
        "columns": [
            "commentid", "createdon", "deleted", "text", "updatedon", "authorid",
            "id", "pullrequestid", "type", "originalauthorid", "createddate",
            "modifieddate", "organizationid", "threadid", "userintegrationid",
            "sentimentscore", "sentimentcomment", "sentimentprocessed",
        ],
        "user_filter": "WHERE authorid = {author_id}",
    },
    "commit": {
        "description": "code commit records",
        "columns": [
            "id", "hash", "authorid", "commitid", "type", "date",
            "skippedregexfiles", "missingcommit", "message", "repoid",
            "createddate", "modifieddate", "repositoryuuid", "repositoryfullname",
            "htmllink", "rework", "newwork", "maintenance", "assistance",
            "linesadded", "linesremoved", "originalauthorid", "processed",
            "skipfromcalculation", "branch", "jiramappingprocessed",
            "organizationid", "workspaceid", "codingfilter", "userintegrationid",
            "jiradatacollected", "estimated_storypoints", "remark",
            "is_auto_excluded",
        ],
        "user_filter": "WHERE authorid = {author_id}",
    },
    "hivelscore": {
        "description": "developer performance and activity scores at org/team level",
        "columns": [
            "orgid", "teamid", "formula_source", "duration_type",
            "score", "startdate", "enddate", "id",
        ],
        "user_filter": "WHERE orgid = {organization_id} AND (teamid = {team_id} OR teamid IS NULL)",
    },
}


def _hash_schema(schema: dict) -> str:
    raw = json.dumps(schema, sort_keys=True).encode()
    return hashlib.md5(raw).hexdigest()


# ── Module-level cache ─────────────────────────────────────────────────────────
_schema: dict = dict(FALLBACK_SCHEMA)
_version_hash: str = _hash_schema(FALLBACK_SCHEMA)


def get_schema() -> dict:
    """Return the current in-memory schema (always populated)."""
    return _schema


def get_version_hash() -> str:
    return _version_hash


def load_from_source_db() -> bool:
    """
    Introspect the 5 Source DB tables at startup.
    Updates _schema in-place. Falls back to FALLBACK_SCHEMA on error.
    Returns True if live DB was reached.
    """
    global _schema, _version_hash

    try:
        import os
        import psycopg2
        dsn = os.getenv("SOURCE_DB_URL")
        if not dsn:
            raise ValueError("SOURCE_DB_URL not set")

        conn = psycopg2.connect(dsn)
        conn.set_session(readonly=True, autocommit=True)
        cur = conn.cursor()

        live_schema: dict = {}
        for table_name, meta in FALLBACK_SCHEMA.items():
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'insightly' AND table_name = %s
                ORDER BY ordinal_position
                """,
                (table_name,),
            )
            rows = cur.fetchall()
            live_cols = [r[0] for r in rows] if rows else meta["columns"]

            live_schema[table_name] = {
                "description": meta["description"],
                "columns": live_cols,
                "user_filter": meta["user_filter"],
            }

        cur.close()
        conn.close()

        _schema = live_schema
        _version_hash = _hash_schema(live_schema)
        logger.info("[schema_cache] Loaded live schema from Source DB (%d tables)", len(live_schema))
        return True

    except Exception as exc:
        logger.warning("[schema_cache] Could not reach Source DB (%s) — using fallback schema", exc)
        _schema = dict(FALLBACK_SCHEMA)
        _version_hash = _hash_schema(FALLBACK_SCHEMA)
        return False


def build_table_selection_prompt() -> str:
    """
    Returns a multi-line string: each table with description + all column names.
    Used in Node 06 Step 1 (Haiku sees ALL columns to make informed table selection).
    """
    lines = []
    for tname, meta in _schema.items():
        col_str = ", ".join(meta["columns"])
        lines.append(
            f"{tname} — {meta['description']}\n"
            f"  columns: {col_str}"
        )
    return "\n\n".join(lines)


def build_agent_schema_for_tables(selected_tables: list[str]) -> str:
    """
    Returns schema string for ONLY the selected tables.
    Injected into Node 06 agent system prompt (selective injection).
    Table names are prefixed with 'insightly.' so the agent generates correct schema-qualified SQL.
    """
    lines = []
    for tname in selected_tables:
        meta = _schema.get(tname)
        if not meta:
            continue
        col_str = ", ".join(meta["columns"])
        lines.append(f"Table: insightly.{tname}\nColumns: {col_str}")
    return "\n\n".join(lines)
