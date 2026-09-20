"""PostgreSQL integration tests for the Task API.

These tests use the `tasks_test` database, never the development `tasks` one.
"""

import os
import subprocess

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg_pool import AsyncConnectionPool

from app import main, repository


def get_test_database_url() -> str:
    base_url, _ = os.environ["DATABASE_URL"].rsplit("/", 1)
    if "@db:" in base_url:
        base_url = base_url.replace("@db:", "@localhost:")
    return f"{base_url}/tasks_test"


@pytest.fixture
def test_database(monkeypatch):
    test_url = get_test_database_url()
    monkeypatch.setenv("DATABASE_URL", test_url)
    repository.DATABASE_URL = test_url

    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        env={**os.environ, "DATABASE_URL": test_url},
        check=True,
    )

    with psycopg.connect(test_url) as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE tasks RESTART IDENTITY")
        cur.execute(
            """
            INSERT INTO tasks (title, done, created_at, updated_at)
            VALUES
                ('Learn FastAPI', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                ('Build CRUD API', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                ('Push to GitHub', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (title) DO NOTHING
            """
        )

    yield

    with psycopg.connect(test_url) as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE tasks RESTART IDENTITY")


@pytest.fixture
def client(test_database):
    with TestClient(main.app) as test_client:
        yield test_client


def test_get_tasks_returns_the_three_seed_tasks(client):
    response = client.get("/tasks")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0]["title"] == "Build CRUD API"
    assert data[1]["title"] == "Learn FastAPI"
    assert data[2]["title"] == "Push to GitHub"


def test_get_task_returns_an_existing_task(client):
    response = client.get("/tasks/1")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["title"] == "Learn FastAPI"
    assert "created_at" in data
    assert "updated_at" in data


def test_get_task_returns_404_for_an_unknown_id(client):
    response = client.get("/tasks/999999")

    assert response.status_code == 404
    assert response.json() == {"error": "Task not found"}


def test_post_creates_a_task_and_persists_it_in_postgres(client):
    response = client.post("/tasks", json={"title": "Learn pytest"})

    assert response.status_code == 201
    created_task = response.json()
    assert created_task["id"] == 4
    assert created_task["title"] == "Learn pytest"
    assert created_task["done"] is False


def test_post_rejects_an_empty_title(client):
    response = client.post("/tasks", json={"title": "   "})

    assert response.status_code == 400
    assert "error" in response.json()


def test_put_updates_title_and_done(client):
    created_task = client.post("/tasks", json={"title": "Old title"}).json()

    response = client.put(
        f"/tasks/{created_task['id']}",
        json={"title": "New title", "done": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created_task["id"]
    assert data["title"] == "New title"
    assert data["done"] is True


def test_put_rejects_an_empty_request_body(client):
    response = client.put("/tasks/1", json={})

    assert response.status_code == 400
    assert "error" in response.json()


def test_put_returns_404_for_an_unknown_id(client):
    response = client.put("/tasks/999999", json={"done": True})

    assert response.status_code == 404
    assert response.json() == {"error": "Task not found"}


def test_delete_removes_a_task(client):
    created_task = client.post("/tasks", json={"title": "Delete me"}).json()

    delete_response = client.delete(f"/tasks/{created_task['id']}")

    assert delete_response.status_code == 204
    assert client.get(f"/tasks/{created_task['id']}").status_code == 404


def test_delete_returns_404_for_an_unknown_id(client):
    response = client.delete("/tasks/999999")

    assert response.status_code == 404
    assert response.json() == {"error": "Task not found"}


def test_stats_are_calculated_by_postgres(client):
    created_task = client.post("/tasks", json={"title": "Complete me"}).json()
    client.put(f"/tasks/{created_task['id']}", json={"done": True})

    response = client.get("/stats")

    assert response.status_code == 200
    assert response.json() == {"total": 4, "completed": 1, "incomplete": 3}


def test_health_reports_database_status(client):
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["postgres"] == "up"
    assert "redis" in data


def test_unknown_route_returns_a_json_404(client):
    response = client.get("/not-a-real-route")

    assert response.status_code == 404
    assert response.json() == {"error": "Route not found"}
