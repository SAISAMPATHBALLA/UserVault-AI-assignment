"""
Runs at startup. Introspects the live PostgreSQL DB and writes db_schema.json.
Works with ANY database — no hardcoded table or column names.

Usage:
    python scripts/generate_schema.py
"""
import os
import sys
import json
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, inspect

DATABASE_URL = os.getenv("DATABASE_URL")
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db_schema.json")

# Tables used internally by the chatbot — excluded from user-visible schema
_INTERNAL_TABLES = {"conversations", "messages", "question_logs", "langgraph_checkpoints",
                    "langgraph_checkpoint_blobs", "langgraph_checkpoint_writes"}


def generate_schema():
    sensitive = set(os.getenv("SENSITIVE_COLUMNS", "password,token,ssn,credit_card,secret,api_key").split(","))
    engine = create_engine(DATABASE_URL)
    insp = inspect(engine)

    schema = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tables": {},
        "sensitive_columns": list(sensitive),
    }

    for table_name in insp.get_table_names():
        if table_name in _INTERNAL_TABLES:
            continue

        columns = {}
        for col in insp.get_columns(table_name):
            col_name = col["name"]
            columns[col_name] = {
                "type": str(col["type"]),
                "nullable": col.get("nullable", True),
                "primary_key": False,
                "sensitive": col_name.lower() in sensitive,
            }

        # Mark primary keys
        pk_constraint = insp.get_pk_constraint(table_name)
        for pk_col in (pk_constraint.get("constrained_columns") or []):
            if pk_col in columns:
                columns[pk_col]["primary_key"] = True

        # Foreign keys
        fk_info = []
        for fk in insp.get_foreign_keys(table_name):
            fk_info.append({
                "columns": fk.get("constrained_columns"),
                "references": f"{fk.get('referred_table')}.{fk.get('referred_columns')}",
            })

        schema["tables"][table_name] = {
            "columns": columns,
            "foreign_keys": fk_info,
        }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(schema, f, indent=2)

    print(f"Schema written to {OUTPUT_PATH} ({len(schema['tables'])} tables)")
    return schema


if __name__ == "__main__":
    generate_schema()
