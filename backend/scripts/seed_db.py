"""
ONE-TIME seed script. Generates realistic dummy data using Faker.
Column definitions are driven by DB_SEED_CONFIG in .env — no hardcoded schema.
Generates a 'users' table with many columns by default.

Usage:
    python scripts/seed_db.py [--rows 500]
"""
import os
import sys
import json
import argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text
from faker import Faker

fake = Faker()
DATABASE_URL = os.getenv("DATABASE_URL")

# Column config: {column_name: faker_method_or_lambda}
# Loaded from DB_SEED_CONFIG env var (JSON) if set, otherwise uses this default.
DEFAULT_SEED_CONFIG = {
    "first_name":       "first_name",
    "last_name":        "last_name",
    "email":            "email",
    "phone":            "phone_number",
    "city":             "city",
    "country":          "country",
    "state":            "state",
    "zip_code":         "postcode",
    "street_address":   "street_address",
    "company":          "company",
    "job_title":        "job",
    "department":       "bs",
    "gender":           "__choice:Male,Female,Non-binary",
    "date_of_birth":    "date_of_birth",
    "registered_at":    "date_time_this_decade",
    "is_active":        "__bool",
    "score":            "__int:0:100",
    "bio":              "text",
    "website":          "url",
    "profile_picture":  "image_url",
}


def _generate_value(col_name: str, spec: str) -> object:
    if spec.startswith("__choice:"):
        options = spec[len("__choice:"):].split(",")
        return fake.random_element(elements=options)
    if spec == "__bool":
        return fake.boolean()
    if spec.startswith("__int:"):
        parts = spec.split(":")
        lo, hi = int(parts[1]), int(parts[2])
        return fake.random_int(min=lo, max=hi)
    method = getattr(fake, spec, None)
    if method:
        val = method()
        return str(val) if not isinstance(val, (bool, int, float)) else val
    return None


def seed(rows: int = 200):
    engine = create_engine(DATABASE_URL)

    seed_config = DEFAULT_SEED_CONFIG
    env_config = os.getenv("DB_SEED_CONFIG")
    if env_config:
        try:
            seed_config = json.loads(env_config)
        except json.JSONDecodeError:
            print("Warning: DB_SEED_CONFIG is not valid JSON, using defaults.")

    columns = list(seed_config.keys())
    col_defs = ", ".join(f"{c} TEXT" for c in columns)
    col_names = ", ".join(columns)
    placeholders = ", ".join(f":{c}" for c in columns)

    with engine.connect() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                {col_defs},
                created_at TIMESTAMP DEFAULT NOW()
            );
        """))
        conn.commit()

        batch = []
        for _ in range(rows):
            row = {col: _generate_value(col, spec) for col, spec in seed_config.items()}
            batch.append(row)

        conn.execute(
            text(f"INSERT INTO users ({col_names}) VALUES ({placeholders})"),
            batch
        )
        conn.commit()

    print(f"Seeded {rows} rows into 'users' table with columns: {', '.join(columns)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=200, help="Number of rows to generate")
    args = parser.parse_args()
    seed(args.rows)
