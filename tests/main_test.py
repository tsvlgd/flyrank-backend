"""PostgreSQL integration tests for the Task API.

Prerequisite: create the `tasks_test` database once in the running Postgres
container. These tests use that database, never the development `tasks` one.
"""

import os
import subprocess

import pytest
from fastapi.testclient import TestClient

from app import main, repository


def get_test_database_url() -> str:
    """Reuse local connection settings but always select the safe test database."""
    base_url, _ = os.environ["DATABASE_URL"].rsplit("/", 1)
    return f"{base_url}/tasks_test"


@pytest.fixture
def test_database(monkeypatch):
    """Give one test a fresh, seeded PostgreSQL tasks_test database.

    Arrange: temporarily replace DATABASE_URL with the test database URL.
    Migrate: Ensure test database has latest schema via Alembic.
    Reset: truncate removes every test row and RESTART IDENTITY resets IDs.
    Seed: recreates exactly the three standard seed rows.
    """
    test_url = get_test_database_url()
    monkeypatch.setenv("DATABASE_URL", test_url)

    # The first call ensures the test db schema is fully migrated.
    subprocess.run(["uv", "run", "alembic", "upgrade", "head"], env={**os.environ, "DATABASE_URL": test_url}, check=True)

    # Each test begins from the same predictable database state.
    with repository.connect() as connection, connection.cursor() as cursor:
        cursor.execute("TRUNCATE TABLE tasks RESTART IDENTITY")
    repository.seed_tasks_if_empty()

    yield

    # Leave the test database empty after the test session's last use too.
    with repository.connect() as connection, connection.cursor() as cursor:
        cursor.execute("TRUNCATE TABLE tasks RESTART IDENTITY")


@pytest.fixture
def client(test_database):
    """Start FastAPI after test_database has selected and prepared tasks_test."""
    with TestClient(main.app) as test_client:
        yield test_client


def test_get_tasks_returns_the_three_seed_tasks(client):
    response = client.get("/tasks")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    # Ordered by title ASC
    assert data[0]["title"] == "Build CRUD API"
    assert data[1]["title"] == "Learn FastAPI"
    assert data[2]["title"] == "Push to GitHub"


def test_get_task_returns_an_existing_task(client):
    # ID 1 was assigned to whichever was inserted first in seed_tasks_if_empty
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

    # This extra assertion proves the row is in Postgres, not only in the API response.
    saved_task = repository.get_task_by_id(created_task["id"])
    assert saved_task["id"] == created_task["id"]
    assert saved_task["title"] == created_task["title"]


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


def test_unknown_route_returns_a_json_404(client):
    response = client.get("/not-a-real-route")

    assert response.status_code == 404
    assert response.json() == {"error": "Route not found"}
