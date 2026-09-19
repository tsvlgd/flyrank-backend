import os

import psycopg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ["DATABASE_URL"]


def connect():
    """Open a PostgreSQL connection using configuration, never a hardcoded URL."""
    return psycopg.connect(DATABASE_URL)


SEED_TASKS = [
    ("Learn FastAPI", False),
    ("Build CRUD API", False),
    ("Push to GitHub", False),
]


def initialise_database() -> None:
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    done BOOLEAN NOT NULL
                )
                """
        )
        cursor.execute("SELECT COUNT(*) FROM tasks")
        task_count = cursor.fetchone()[0]

        if task_count == 0:
            cursor.executemany(
                "INSERT INTO tasks (title, done) VALUES (%s, %s)",
                SEED_TASKS,
            )
