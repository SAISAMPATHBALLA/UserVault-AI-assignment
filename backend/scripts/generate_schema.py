"""
Introspects the 5 Source DB tables (AWS RDS) and populates the in-memory schema_cache.
Called once at server startup. Can also be run standalone for debugging.

Usage:
    python scripts/generate_schema.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

import schema_cache


def generate_schema() -> bool:
    """
    Connects to Source DB (SOURCE_DB_URL) and populates schema_cache._schema.
    Returns True if live DB reached, False if fallback used.
    """
    return schema_cache.load_from_source_db()


if __name__ == "__main__":
    success = generate_schema()
    schema = schema_cache.get_schema()
    print(f"Schema loaded ({'live DB' if success else 'FALLBACK'}):")
    for table, meta in schema.items():
        cols = meta.get("columns", [])
        print(f"  {table}: {len(cols)} columns — {', '.join(cols[:5])}{'...' if len(cols) > 5 else ''}")
