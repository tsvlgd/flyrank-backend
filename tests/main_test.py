"""Automated checks for app.main.

Run with:
    uv run pytest -v

These tests never use the real tasks.db file. Each test gets its own empty,
temporary SQLite database, then FastAPI starts normally and seeds that database.
"""

import sqlite3

import pytest
from fastapi.testclient import TestClient
from app import main


@pytest.fixture
def test_database(monkeypatch, tmp_path):
    """Point the app at a temporary database for this one test."""
    database_path = tmp_path / "test_tasks.db"
    monkeypatch.setattr(main, "DATABASE_PATH", database_path)
    return database_path


@pytest.fixture
def client(test_database):
    """Start the FastAPI app, including its normal startup database setup."""
    with TestClient(main.app) as test_client:
        yield test_client


def test_get_tasks_returns_the_three_seed_tasks(client):
    response = client.get("/tasks")

    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 3
    assert tasks[0] == {"id": 1, "title": "Learn FastAPI", "done": False}


def test_get_task_returns_one_existing_task(client):
    response = client.get("/tasks/1")

    assert response.status_code == 200
    assert response.json()["title"] == "Learn FastAPI"


def test_get_task_returns_404_for_an_unknown_id(client):
    response = client.get("/tasks/999999")

    assert response.status_code == 404
    assert response.json() == {"error": "Task not found"}


def test_post_creates_a_task_and_saves_it_in_sqlite(client, test_database):
    response = client.post("/tasks", json={"title": "Learn pytest"})

    assert response.status_code == 201
    created_task = response.json()
    assert created_task["title"] == "Learn pytest"
    assert created_task["done"] is False

    connection = sqlite3.connect(test_database)
    saved_task = connection.execute(
        "SELECT title, done FROM tasks WHERE id = ?", (created_task["id"],)
    ).fetchone()
    connection.close()

    assert saved_task == ("Learn pytest", 0)


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
    assert response.json() == {
        "id": created_task["id"],
        "title": "New title",
        "done": True,
    }


def test_put_rejects_an_empty_request_body(client):
    response = client.put("/tasks/1", json={})

    assert response.status_code == 400
    assert "error" in response.json()


def test_delete_removes_a_task(client):
    created_task = client.post("/tasks", json={"title": "Delete me"}).json()

    delete_response = client.delete(f"/tasks/{created_task['id']}")

    assert delete_response.status_code == 204
    assert client.get(f"/tasks/{created_task['id']}").status_code == 404


def test_database_seeds_only_once(client, test_database):
    main.initialise_database()

    connection = sqlite3.connect(test_database)
    task_count = connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    connection.close()

    assert task_count == 3


def test_unknown_route_returns_json_404(client):
    response = client.get("/not-a-real-route")

    assert response.status_code == 404
    assert response.json() == {"error": "Route not found"}
