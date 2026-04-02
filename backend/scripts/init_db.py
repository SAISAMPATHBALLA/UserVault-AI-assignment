"""
ONE-TIME database initialization script.
Creates the pgvector extension and all application tables.
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

DATABASE_URL = os.getenv("DATABASE_URL")


def create_database_if_missing():
    url = make_url(DATABASE_URL)
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
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        # Enable pgvector
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

        # conversations
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS conversations (
                id                      SERIAL PRIMARY KEY,
                session_id              UUID NOT NULL UNIQUE,
                title                   TEXT,
                is_deleted              BOOLEAN DEFAULT FALSE,
                history_summary         TEXT DEFAULT '',
                summarized_until_msg_id INTEGER DEFAULT 0,
                created_at              TIMESTAMP DEFAULT NOW(),
                updated_at              TIMESTAMP DEFAULT NOW()
            );
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

        # question_logs (semantic cache + audit)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS question_logs (
                id             SERIAL PRIMARY KEY,
                question       TEXT NOT NULL,
                question_emb   vector(1536),
                intent         VARCHAR(50),
                answered       BOOLEAN NOT NULL DEFAULT FALSE,
                validated      BOOLEAN,
                sql_generated  TEXT,
                answer         TEXT,
                cache_hit      VARCHAR(20),
                hit_count      INTEGER DEFAULT 1,
                threat         BOOLEAN DEFAULT FALSE,
                asked_at       TIMESTAMP DEFAULT NOW()
            );
        """))

        # ANN index for fast similarity search
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS question_logs_emb_idx
            ON question_logs USING ivfflat (question_emb vector_cosine_ops)
            WITH (lists = 100);
        """))

        conn.commit()

    print("Database initialized successfully.")


if __name__ == "__main__":
    init()
