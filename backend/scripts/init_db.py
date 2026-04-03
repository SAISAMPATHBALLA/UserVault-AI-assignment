"""
ONE-TIME App DB initialization script.
Creates pgvector extension + all application-owned tables.
Idempotent — safe to run multiple times.

Usage:
    python scripts/init_db.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

APP_DB_URL = os.getenv("APP_DB_URL")


def create_database_if_missing():
    url = make_url(APP_DB_URL)
    db_name = url.database
    admin_url = url.set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": db_name}
        ).fetchone()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
            print(f"Created database: {db_name}")
    admin_engine.dispose()


def init():
    create_database_if_missing()
    engine = create_engine(APP_DB_URL)

    with engine.connect() as conn:
        # pgvector extension
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

        # conversations — author_id ties session to user
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS conversations (
                id                      SERIAL PRIMARY KEY,
                session_id              UUID NOT NULL UNIQUE,
                author_id               INTEGER NOT NULL,
                title                   TEXT,
                is_deleted              BOOLEAN DEFAULT FALSE,
                history_summary         TEXT DEFAULT '',
                summarized_until_msg_id INTEGER DEFAULT 0,
                created_at              TIMESTAMP DEFAULT NOW(),
                updated_at              TIMESTAMP DEFAULT NOW()
            );
        """))

        # B-tree index for fast session → author lookup
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS conversations_author_idx
            ON conversations (author_id);
        """))

        # messages
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS messages (
                id               SERIAL PRIMARY KEY,
                conversation_id  INTEGER REFERENCES conversations(id),
                role             VARCHAR(20) NOT NULL,
                raw_question     TEXT,
                reconstructed_q  TEXT,
                content          TEXT NOT NULL,
                intent           VARCHAR(50),
                cache_hit        VARCHAR(20),
                is_deleted       BOOLEAN DEFAULT FALSE,
                created_at       TIMESTAMP DEFAULT NOW()
            );
        """))

        # question_logs — semantic cache + audit log
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS question_logs (
                id             SERIAL PRIMARY KEY,
                author_id      INTEGER NOT NULL,
                question       TEXT NOT NULL,
                question_emb   vector(384),
                intent         VARCHAR(50),
                answered       BOOLEAN NOT NULL DEFAULT FALSE,
                validated      BOOLEAN,
                sql_generated  TEXT,
                answer         TEXT,
                cache_hit      VARCHAR(20),
                hit_count      INTEGER DEFAULT 1,
                threat         BOOLEAN DEFAULT FALSE,
                expires_at     TIMESTAMP,
                asked_at       TIMESTAMP DEFAULT NOW()
            );
        """))

        # ANN index for cosine similarity search
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS question_logs_emb_idx
            ON question_logs USING ivfflat (question_emb vector_cosine_ops)
            WITH (lists = 100);
        """))

        # B-tree index for user-scoped ANN pre-filter
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS question_logs_author_idx
            ON question_logs (author_id);
        """))

        conn.commit()

    print("App DB initialized successfully.")


if __name__ == "__main__":
    init()
