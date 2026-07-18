from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="Task API",
    version="1.0.0",
    description="A simple CRUD API built with FastAPI.",
)


# Pydantic Models


class Task(BaseModel):
    """Represents a task."""

    id: int
    title: str
    done: bool


class TaskCreate(BaseModel):
    """Schema for creating a new task."""

    title: str


class TaskUpdate(BaseModel):
    """Schema for updating an existing task."""

    title: str | None = None
    done: bool | None = None


# In-Memory Database


tasks = [
    {
        "id": 1,
        "title": "Learn FastAPI",
        "done": False,
    },
    {
        "id": 2,
        "title": "Build CRUD API",
        "done": False,
    },
    {
        "id": 3,
        "title": "Push to GitHub",
        "done": False,
    },
]


# Routes


@app.get(
    "/",
    summary="API Information",
    description="Returns basic information about the API.",
)
def root():
    """Return API metadata."""
    return {
        "name": "Task API",
        "version": "1.0",
        "endpoints": ["/tasks"],
    }


@app.get(
    "/health",
    summary="Health Check",
    description="Returns the current health status of the API.",
)
def get_health():
    """Return the health status of the API."""
    return {
        "status": "Okay",
        "service": "Task API",
        "version": "1.0",
    }


@app.get(
    "/tasks",
    response_model=list[Task],
    summary="Get all tasks",
    description="Returns all available tasks.",
)
def get_tasks():
    """Return all tasks."""
    return tasks


@app.get(
    "/tasks/{task_id}",
    response_model=Task,
    summary="Get task by ID",
    description="Returns a task matching the provided ID.",
)
def get_task(task_id: int):
    """Return a single task."""

    for task in tasks:
        if task["id"] == task_id:
            return task

    raise HTTPException(
        status_code=404,
        detail=f"Task {task_id} not found.",
    )


@app.post(
    "/tasks",
    response_model=Task,
    status_code=201,
    summary="Create a task",
    description="Creates a new task.",
)
def create_task(task: TaskCreate):
    """Create a new task."""

    if not task.title.strip():
        raise HTTPException(
            status_code=400,
            detail="Title cannot be empty.",
        )

    new_task = {
        "id": len(tasks) + 1,
        "title": task.title,
        "done": False,
    }

    tasks.append(new_task)

    return new_task


@app.put(
    "/tasks/{task_id}",
    response_model=Task,
    summary="Update a task",
    description="Updates a task's title, completion status, or both.",
)
def update_task(task_id: int, updated_task: TaskUpdate):
    """Update an existing task."""

    if updated_task.title is None and updated_task.done is None:
        raise HTTPException(
            status_code=400,
            detail="At least one field must be provided for update.",
        )

    for task in tasks:
        if task["id"] == task_id:
            if updated_task.title is not None:
                if not updated_task.title.strip():
                    raise HTTPException(
                        status_code=400,
                        detail="Title cannot be empty.",
                    )
                task["title"] = updated_task.title

            if updated_task.done is not None:
                task["done"] = updated_task.done

            return task

    raise HTTPException(
        status_code=404,
        detail=f"Task {task_id} not found.",
    )


@app.delete(
    "/tasks/{task_id}",
    status_code=204,
    summary="Delete a task",
    description="Deletes a task by its ID.",
)
def delete_task(task_id: int):
    """Delete a task."""

    for index, task in enumerate(tasks):
        if task["id"] == task_id:
            tasks.pop(index)
            return

    raise HTTPException(
        status_code=404,
        detail=f"Task {task_id} not found.",
    )
