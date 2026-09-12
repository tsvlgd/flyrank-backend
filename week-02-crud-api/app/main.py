import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

# Setup secure application logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TaskAPI")

app = FastAPI(
    title="Task API",
    version="1.0.0",
    description="A robust, production-ready CRUD API built with FastAPI.",
)


# Global 404 Route Not Found Fallback Layer
@app.exception_handler(404)
async def custom_404_handler(request: Request, __):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND, content={"error": "Route not found"}
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


# --- IN-MEMORY MOCK DATABASE ---
tasks: list[dict[str, Any]] = [
    {"id": 1, "title": "Learn FastAPI", "done": False},
    {"id": 2, "title": "Build CRUD API", "done": False},
    {"id": 3, "title": "Push to GitHub", "done": False},
]


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
def get_tasks():
    """Fetches every single task from the persistence store."""
    try:
        return tasks
    except Exception as e:
        logger.error(f"Database read failure: {e}")
        raise


@app.get(
    "/tasks/{task_id}", response_model=Task, summary="Get task by ID", tags=["Tasks"]
)
def get_task(task_id: int):
    """Fetches a solitary task record corresponding to the provided ID."""
    try:
        for task in tasks:
            if task["id"] == task_id:
                return task

        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"error": "Task not found"}
        )
    except Exception as e:
        logger.error(f"Failed to fetch task {task_id}: {e}")
        raise


@app.post(
    "/tasks",
    response_model=Task,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task",
    tags=["Tasks"],
)
def create_task(task_data: TaskCreate):
    """Generates and stores a brand new task record."""
    try:
        new_id = max((t["id"] for t in tasks), default=0) + 1
        new_task = {
            "id": new_id,
            "title": task_data.title,
            "done": False,
        }
        tasks.append(new_task)
        return new_task
    except Exception as e:
        logger.error(f"Task creation transaction aborted: {e}")
        raise


@app.put(
    "/tasks/{task_id}", response_model=Task, summary="Update a task", tags=["Tasks"]
)
def update_task(task_id: int, updated_data: TaskUpdate):
    """Updates a task's title status, completion flag context, or both."""
    try:
        if updated_data.title is None and updated_data.done is None:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "At least one valid field must be provided to initiate an update."
                },
            )

        for task in tasks:
            if task["id"] == task_id:
                if updated_data.title is not None:
                    task["title"] = updated_data.title
                if updated_data.done is not None:
                    task["done"] = updated_data.done
                return task

        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"error": "Task not found"}
        )
    except Exception as e:
        logger.error(f"Task updates failed for ID {task_id}: {e}")
        raise


@app.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
    tags=["Tasks"],
)
def delete_task(task_id: int):
    """Purges a unique task from the persistence registry via ID match."""
    try:
        for index, task in enumerate(tasks):
            if task["id"] == task_id:
                tasks.pop(index)
                return None

        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"error": "Task not found"}
        )
    except Exception as e:
        logger.error(f"Deletion lifecycle crash for ID {task_id}: {e}")
        raise
