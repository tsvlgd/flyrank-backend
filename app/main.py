import logging
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

# Setup secure application logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TaskAPI")


# SQLite creates this file automatically when the application starts.
DATABASE_PATH = Path(__file__).resolve().parent.parent / "tasks.db"
SEED_TASKS = [
    ("Learn FastAPI", False),
    ("Build CRUD API", False),
    ("Push to GitHub", False),
]


def initialise_database() -> None:
    """Create the table and add example tasks only on the first run."""
    # We open a temporary standalone connection just for initialization
    connection = sqlite3.connect(DATABASE_PATH)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                done BOOLEAN NOT NULL
            )
            """
        )
        # Fetch count safely
        task_count = connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if task_count == 0:
            connection.executemany(
                "INSERT INTO tasks (title, done) VALUES (?, ?)", SEED_TASKS
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
    initialise_database()
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


@app.get("/tasks", response_model=list[Task], summary="Get all tasks", tags=["Tasks"])
def get_tasks(connection: sqlite3.Connection = Depends(database_connection)):
    """Fetches every single task from the persistence store."""
    rows = connection.execute("SELECT * FROM tasks").fetchall()
    return [dict(row) for row in rows]


@app.get(
    "/tasks/{task_id}", response_model=Task, summary="Get task by ID", tags=["Tasks"]
)
def get_task(
    task_id: int, connection: sqlite3.Connection = Depends(database_connection)
):
    """Fetches a solitary task record corresponding to the provided ID."""
    task = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

    if task is not None:
        return dict(task)

    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND, content={"error": "Task not found"}
    )


@app.post(
    "/tasks",
    response_model=Task,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task",
    tags=["Tasks"],
)
def create_task(
    task_data: TaskCreate,
    connection: sqlite3.Connection = Depends(database_connection),
):
    """Generates and stores a brand new task record."""
    cursor = connection.execute(
        "INSERT INTO tasks (title, done) VALUES (?, ?)",
        (task_data.title, False),
    )
    task = connection.execute(
        "SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    connection.commit()
    return dict(task)


@app.put(
    "/tasks/{task_id}", response_model=Task, summary="Update a task", tags=["Tasks"]
)
def update_task(
    task_id: int,
    updated_data: TaskUpdate,
    connection: sqlite3.Connection = Depends(database_connection),
):
    """Updates a task's title status, completion flag context, or both."""
    if updated_data.title is None and updated_data.done is None:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "At least one valid field must be provided to initiate an update."
            },
        )

    task = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if task is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"error": "Task not found"}
        )

    title = updated_data.title if updated_data.title is not None else task["title"]
    done = updated_data.done if updated_data.done is not None else task["done"]
    connection.execute(
        "UPDATE tasks SET title = ?, done = ? WHERE id = ?", (title, done, task_id)
    )
    connection.commit()
    return {"id": task_id, "title": title, "done": done}


@app.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
    tags=["Tasks"],
)
def delete_task(
    task_id: int,
    connection: sqlite3.Connection = Depends(database_connection),
):
    """Purges a unique task from the persistence registry via ID match."""
    cursor = connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    connection.commit()
    if cursor.rowcount == 1:
        return None

    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND, content={"error": "Task not found"}
    )
