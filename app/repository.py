import os

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

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


# TODO

""" 
1. Only after core CRUD works, bring back your optional SQLite extras—timestamps, filters, search, ordering—in PostgreSQL form.
2. equivalent PostgreSQL endpoint has to be tested.
"""


def get_stats():
    with connect() as connection, connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT 
            COUNT(*) AS total,
            SUM(CASE WHEN done THEN 1 ELSE 0 END) AS completed
            FROM tasks;
            """
        )

        row = cursor.fetchone()
        total = row["total"] if row["total"] else 0
        completed = row["completed"] if row["completed"] else 0

        leftovers = total - completed
        return {"total": total, "completed": completed, "incomplete": leftovers}


def get_all_tasks():
    with connect() as connection, connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute("SELECT * FROM tasks ORDER BY id")
        return cursor.fetchall()


def get_task_by_id(task_id: int):
    with connect() as connection, connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
        return cursor.fetchone()


def create_task(title: str):
    with connect() as connection, connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
                INSERT INTO tasks (title, done)
                VALUES (%s, %s)
                RETURNING id
                """,
            (title, False),
        )
        new_id = cursor.fetchone()["id"]
        cursor.execute("SELECT * FROM tasks WHERE id = %s", (new_id,))
        return cursor.fetchone()


def update_task(task_id: int, title: str | None, done: bool | None):
    with connect() as connection, connection.cursor(row_factory=dict_row) as cursor:
        # A one-item parameter tuple needs a trailing comma: (task_id,).
        cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
        existing_task = cursor.fetchone()
        if existing_task is None:
            return None

        final_title = title if title is not None else existing_task["title"]
        final_done = done if done is not None else existing_task["done"]

        cursor.execute(
            """
            UPDATE tasks
            SET title = %s, done = %s
            WHERE id = %s
            RETURNING *
            """,
            (final_title, final_done, task_id),
        )
        # Fetch while the cursor is still open, then return the updated row.
        return cursor.fetchone()


def delete_task(task_id: int) -> bool:
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        return cursor.rowcount == 1
