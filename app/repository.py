import os

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

load_dotenv()


def connect():
    """Open a connection using the DATABASE_URL active for this operation."""
    return psycopg.connect(os.environ["DATABASE_URL"])


SEED_TASKS = [
    ("Learn FastAPI", False),
    ("Build CRUD API", False),
    ("Push to GitHub", False),
]


def seed_tasks_if_empty() -> None:
    """Insert example rows only after migrations have created an empty table."""
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM tasks")
        task_count = cursor.fetchone()[0]

        if task_count == 0:
            cursor.executemany(
                """
                INSERT INTO tasks (title, done, created_at, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                SEED_TASKS,
            )

def get_stats():
    with connect() as connection, connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT
            COUNT(*) AS total,
            COALESCE(SUM(CASE WHEN done THEN 1 ELSE 0 END), 0) AS completed
            FROM tasks
            """
        )

        row = cursor.fetchone()
        return {
            "total": row["total"],
            "completed": row["completed"],
            "incomplete": row["total"] - row["completed"],
        }


def get_all_tasks(search: str | None = None, done: bool | None = None):
    with connect() as connection, connection.cursor(row_factory=dict_row) as cursor:
        sql = "SELECT * FROM tasks"
        conditions: list[str] = []
        parameters: list[str | bool] = []

        if search is not None:
            # ILIKE keeps the old SQLite search experience case-insensitive.
            conditions.append("title ILIKE %s")
            parameters.append(f"%{search}%")
        if done is not None:
            conditions.append("done = %s")
            parameters.append(done)

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY title ASC"

        cursor.execute(sql, parameters)
        return cursor.fetchall()


def get_task_by_id(task_id: int):
    with connect() as connection, connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
        return cursor.fetchone()


def create_task(title: str):
    with connect() as connection, connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
                INSERT INTO tasks (title, done, created_at, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING *
                """,
            (title, False),
        )
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
            SET title = %s, done = %s, updated_at = CURRENT_TIMESTAMP
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
