import os

from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

pool: AsyncConnectionPool | None = None


def get_pool() -> AsyncConnectionPool:
    if pool is None:
        raise RuntimeError("Database connection pool is not initialized.")
    return pool


SEED_TASKS = [
    ("Learn FastAPI", False),
    ("Build CRUD API", False),
    ("Push to GitHub", False),
]


async def seed_tasks_if_empty() -> None:
    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM tasks")
            count = (await cur.fetchone())[0]
            if count == 0:
                await cur.executemany(
                    """
                    INSERT INTO tasks (title, done, created_at, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (title) DO NOTHING
                    """,
                    SEED_TASKS,
                )


async def check_db() -> bool:
    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1")
            return (await cur.fetchone())[0] == 1


async def get_stats():
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT
                COUNT(*) AS total,
                COALESCE(SUM(CASE WHEN done THEN 1 ELSE 0 END), 0) AS completed
                FROM tasks
                """
            )
            row = await cur.fetchone()
            return {
                "total": row["total"],
                "completed": row["completed"],
                "incomplete": row["total"] - row["completed"],
            }


async def get_all_tasks(search: str | None = None, done: bool | None = None):
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            sql = "SELECT * FROM tasks"
            conditions: list[str] = []
            parameters: list[str | bool] = []

            if search is not None:
                conditions.append("title ILIKE %s")
                parameters.append(f"%{search}%")
            if done is not None:
                conditions.append("done = %s")
                parameters.append(done)

            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY title ASC"

            await cur.execute(sql, parameters)
            return await cur.fetchall()


async def get_task_by_id(task_id: int):
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
            return await cur.fetchone()


async def create_task(title: str):
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                INSERT INTO tasks (title, done, created_at, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING *
                """,
                (title, False),
            )
            return await cur.fetchone()


async def update_task(task_id: int, title: str | None, done: bool | None):
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
            existing_task = await cur.fetchone()
            if existing_task is None:
                return None

            final_title = title if title is not None else existing_task["title"]
            final_done = done if done is not None else existing_task["done"]

            await cur.execute(
                """
                UPDATE tasks
                SET title = %s, done = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING *
                """,
                (final_title, final_done, task_id),
            )
            return await cur.fetchone()


async def delete_task(task_id: int) -> bool:
    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
            return cur.rowcount == 1
