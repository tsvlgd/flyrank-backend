import logging
from contextlib import asynccontextmanager
from datetime import datetime

import redis.asyncio as redis
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field, field_validator

from . import repository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TaskAPI")

redis_client: redis.Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client

    repository.pool = AsyncConnectionPool(
        conninfo=repository.DATABASE_URL,
        min_size=2,
        max_size=10,
        open=False,
    )
    await repository.pool.open()
    await repository.seed_tasks_if_empty()

    redis_url = "redis://redis:6379" if "db:" in repository.DATABASE_URL else "redis://localhost:6379"
    redis_client = redis.from_url(redis_url)
    try:
        pong = await redis_client.ping()
        logger.info(f"Redis connected: {pong}")
    except Exception as exc:
        logger.warning(f"Redis unavailable: {exc}")
        redis_client = None

    yield

    await repository.pool.close()
    if redis_client:
        await redis_client.aclose()


app = FastAPI(
    title="Task API",
    version="2.0.0",
    description="A production-ready async CRUD API with connection pooling and Redis.",
    lifespan=lifespan,
)


@app.exception_handler(404)
async def custom_404_handler(request: Request, __):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND, content={"error": "Route not found"}
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, __):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "Invalid task data"},
    )


@app.middleware("http")
async def safe_exception_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        logger.error(
            f"CRASH on {request.url.path} | Reason: {type(exc).__name__}: {exc}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Internal server error"},
        )


class Task(BaseModel):
    id: int
    title: str = Field(
        ..., min_length=1, description="The title of the task cannot be empty."
    )
    done: bool = Field(default=False)
    created_at: datetime
    updated_at: datetime


class TaskStats(BaseModel):
    total: int
    completed: int
    incomplete: int


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, description="Task title is required.")

    @field_validator("title")
    @classmethod
    def validate_title_not_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Title cannot consist solely of whitespace.")
        return stripped


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    done: bool | None = Field(default=None)

    @field_validator("title")
    @classmethod
    def validate_optional_title(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Updated title cannot be empty.")
        return value if value is None else value.strip()


@app.get("/", summary="API Information", tags=["System"])
async def root():
    return {
        "name": "Task API",
        "version": "2.0",
        "endpoints": ["/tasks"],
    }


@app.get("/health", summary="Health Check", tags=["System"])
async def get_health():
    db_ok = False
    redis_ok = False
    try:
        db_ok = await repository.check_db()
    except Exception:
        pass
    try:
        if redis_client:
            redis_ok = await redis_client.ping()
    except Exception:
        pass
    return {
        "status": "healthy" if db_ok else "degraded",
        "service": "Task API",
        "postgres": "up" if db_ok else "down",
        "redis": "up" if redis_ok else "down",
    }


@app.get(
    "/stats",
    response_model=TaskStats,
    summary="Task stats",
    tags=["Tasks"],
)
async def get_stats():
    return await repository.get_stats()


@app.get("/tasks", response_model=list[Task], summary="Get all tasks", tags=["Tasks"])
async def get_tasks(search: str | None = None, done: bool | None = None):
    return await repository.get_all_tasks(search, done)


@app.get(
    "/tasks/{task_id}", response_model=Task, summary="Get task by ID", tags=["Tasks"]
)
async def get_task(task_id: int):
    task = await repository.get_task_by_id(task_id)
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
async def create_task(task_data: TaskCreate):
    return await repository.create_task(task_data.title)


@app.put(
    "/tasks/{task_id}", response_model=Task, summary="Update a task", tags=["Tasks"]
)
async def update_task(task_id: int, updated_data: TaskUpdate):
    if updated_data.title is None and updated_data.done is None:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "At least one valid field must be provided to initiate an update."
            },
        )
    task = await repository.update_task(task_id, updated_data.title, updated_data.done)
    if task is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"error": "Task not found"}
        )
    return task


@app.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
    tags=["Tasks"],
)
async def delete_task(task_id: int):
    if await repository.delete_task(task_id):
        return None
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND, content={"error": "Task not found"}
    )
