import logging
import sqlite3
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from . import repository

# Setup secure application logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TaskAPI")


def utc_now() -> str:
    """Return a timezone-aware timestamp in a sortable ISO-8601 format."""
    return datetime.now(UTC).isoformat()


def migrate_timestamp_columns(connection: sqlite3.Connection) -> None:
    """Add and backfill timestamps for databases created before this extra."""
    column_names = {
        row[1] for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
    }
    migration_time = utc_now()

    # Existing rows receive NULL for newly added SQLite columns; fill them below.
    if "created_at" not in column_names:
        connection.execute("ALTER TABLE tasks ADD COLUMN created_at TEXT")
    if "updated_at" not in column_names:
        connection.execute("ALTER TABLE tasks ADD COLUMN updated_at TEXT")

    connection.execute(
        "UPDATE tasks SET created_at = ? WHERE created_at IS NULL OR created_at = ''",
        (migration_time,),
    )
    connection.execute(
        "UPDATE tasks SET updated_at = ? WHERE updated_at IS NULL OR updated_at = ''",
        (migration_time,),
    )


def initialise_database() -> None:
    """Create or upgrade the table, then seed an empty database once."""
    # We open a temporary standalone connection just for initialization
    connection = sqlite3.connect(DATABASE_PATH)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                done BOOLEAN NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        migrate_timestamp_columns(connection)
        task_count = connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if task_count == 0:
            seed_time = utc_now()
            connection.executemany(
                """
                INSERT INTO tasks (title, done, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                [(title, done, seed_time, seed_time) for title, done in SEED_TASKS],
            )
        connection.commit()
    finally:
        connection.close()


def database_connection():
    """
    FastAPI dependency that opens a fresh, isolated connection per request.
    Automatically closes the connection when the request finishes.
    """
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    repository.initialise_database()
    yield


app = FastAPI(
    title="Task API",
    version="1.0.0",
    description="A robust, production-ready CRUD API built with FastAPI.",
    lifespan=lifespan,
)


# Global 404 Route Not Found Fallback Layer
@app.exception_handler(404)
async def custom_404_handler(request: Request, __):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND, content={"error": "Route not found"}
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, __):
    """invalid-body contract."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "Invalid task data"},
    )


@app.middleware("http")
async def safe_exception_middleware(request: Request, call_next):
    try:
        # Pass the request down the pipeline
        return await call_next(request)
    except Exception as exc:
        # 1. Print ONLY your clean, single-line error log
        logger.error(
            f"💥 CRASH on {request.url.path} | Reason: {type(exc).__name__}: {exc}"
        )

        # 2. Return clean JSON payload (Swallowing the traceback)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Internal server error"},
        )


class Task(BaseModel):
    """Represents a validated task record."""

    id: int
    title: str = Field(
        ..., min_length=1, description="The title of the task cannot be empty."
    )
    done: bool = Field(default=False)
    # created_at: str
    # updated_at: str


class TaskStats(BaseModel):
    """Summary counts calculated by SQLite."""

    total: int
    completed: int
    incomplete: int


class TaskCreate(BaseModel):
    """Schema for creating a new task with built-in request validation."""

    title: str = Field(..., min_length=1, description="Task title is required.")

    @field_validator("title")
    @classmethod
    def validate_title_not_empty(cls, value: str) -> str:
        """Strips whitespace and ensures the title contains actual text."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("Title cannot consist solely of whitespace.")
        return stripped


class TaskUpdate(BaseModel):
    """Schema for updating an existing task record."""

    title: str | None = Field(default=None, min_length=1)
    done: bool | None = Field(default=None)

    @field_validator("title")
    @classmethod
    def validate_optional_title(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Updated title cannot be empty.")
        return value if value is None else value.strip()


@app.get("/", summary="API Information", tags=["System"])
def root():
    """Returns basic metadata about the API ecosystem."""
    return {
        "name": "Task API",
        "version": "1.0",
        "endpoints": ["/tasks"],
    }


@app.get("/health", summary="Health Check", tags=["System"])
def get_health():
    """Returns the direct system operational status."""
    return {
        "status": "Healthy",
        "service": "Task API",
    }


@app.get(
    "/stats",
    response_model=TaskStats,
    summary="Task stats",
    tags=["Tasks"],
)
def get_stats(connection: sqlite3.Connection = Depends(database_connection)):
    """Returns task counts calculated by SQL, not by Python loops."""
    cursor = connection.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN done = 1 THEN 1 ELSE 0 END) AS completed
        FROM tasks;
        """
    )

    row = cursor.fetchone()

    total = row["total"] if row["total"] else 0
    completed = row["completed"] if row["completed"] else 0
    incomplete = total - completed

    return {"total": total, "completed": completed, "incomplete": incomplete}


@app.get("/tasks", response_model=list[Task], summary="Get all tasks", tags=["Tasks"])
def get_tasks():
    return repository.get_all_tasks()


@app.get(
    "/tasks/{task_id}", response_model=Task, summary="Get task by ID", tags=["Tasks"]
)
def get_task(task_id: int):
    task = repository.get_task_by_id(task_id)
    if task is None:
        return JSONResponse(status_code=404, content={"error": "Task not found"})
    return task


@app.post(
    "/tasks",
    response_model=Task,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task",
    tags=["Tasks"],
)
def create_task(task_data: TaskCreate):
    return repository.create_task(task_data.title)


@app.put(
    "/tasks/{task_id}", response_model=Task, summary="Update a task", tags=["Tasks"]
)
def update_task(task_id: int, updated_data: TaskUpdate):
    """Updates a task's title status, completion flag context, or both."""
    if updated_data.title is None and updated_data.done is None:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "At least one valid field must be provided to initiate an update."
            },
        )
    task = repository.update_task(task_id, updated_data.title, updated_data.done)
    if task is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"error": "Task not found"}
        )
    return {"id": task["id"], "title": task["title"], "done": task["done"]}


@app.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
    tags=["Tasks"],
)
def delete_task(task_id: int):
    """Purges a unique task from the persistence registry via ID match."""
    if repository.delete_task(task_id):
        return None

    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND, content={"error": "Task not found"}
    )
