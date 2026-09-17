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
    assert [task["title"] for task in tasks] == [
        "Build CRUD API",
        "Learn FastAPI",
        "Push to GitHub",
    ]


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
    assert created_task["created_at"] == created_task["updated_at"]

    connection = sqlite3.connect(test_database)
    saved_task = connection.execute(
        """
        SELECT title, done, created_at, updated_at
        FROM tasks WHERE id = ?
        """,
        (created_task["id"],),
    ).fetchone()
    connection.close()

    assert saved_task == (
        "Learn pytest",
        0,
        created_task["created_at"],
        created_task["updated_at"],
    )


def test_post_rejects_an_empty_title(client):
    response = client.post("/tasks", json={"title": "   "})

    assert response.status_code == 400
    assert "error" in response.json()


def test_put_updates_title_done_and_updated_timestamp(client, monkeypatch):
    # A controlled clock makes this timestamp test deterministic.
    timestamps = iter(["2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00"])
    monkeypatch.setattr(main, "utc_now", lambda: next(timestamps))

    created_task = client.post("/tasks", json={"title": "Old title"}).json()

    response = client.put(
        f"/tasks/{created_task['id']}",
        json={"title": "New title", "done": True},
    )

    assert response.status_code == 200
    updated_task = response.json()
    assert updated_task["id"] == created_task["id"]
    assert updated_task["title"] == "New title"
    assert updated_task["done"] is True
    assert updated_task["created_at"] == "2026-01-01T00:00:00+00:00"
    assert updated_task["updated_at"] == "2026-01-02T00:00:00+00:00"


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


def test_startup_migrates_an_existing_database_without_losing_tasks(
    monkeypatch, tmp_path
):
    database_path = tmp_path / "old_tasks.db"
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            done BOOLEAN NOT NULL
        )
        """
    )
    connection.execute(
        "INSERT INTO tasks (title, done) VALUES (?, ?)", ("Existing task", False)
    )
    connection.commit()
    connection.close()
    monkeypatch.setattr(main, "DATABASE_PATH", database_path)
    monkeypatch.setattr(main, "utc_now", lambda: "2026-01-01T00:00:00+00:00")

    with TestClient(main.app) as migration_client:
        response = migration_client.get("/tasks/1")

    assert response.status_code == 200
    assert response.json() == {
        "id": 1,
        "title": "Existing task",
        "done": False,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }


def test_unknown_route_returns_json_404(client):
    response = client.get("/not-a-real-route")

    assert response.status_code == 404
    assert response.json() == {"error": "Route not found"}


def test_get_tasks_searches_by_title(client):
    client.post("/tasks", json={"title": "Buy milk"})

    response = client.get("/tasks?search=milk")

    assert response.status_code == 200
    assert [task["title"] for task in response.json()] == ["Buy milk"]


def test_get_tasks_filters_by_completion_status(client):
    created_task = client.post("/tasks", json={"title": "Finish report"}).json()
    client.put(f"/tasks/{created_task['id']}", json={"done": True})

    completed_response = client.get("/tasks?done=true")
    incomplete_response = client.get("/tasks?done=false")

    assert [task["id"] for task in completed_response.json()] == [created_task["id"]]
    assert all(task["done"] is False for task in incomplete_response.json())


def test_get_tasks_combines_search_and_completion_filters(client):
    incomplete_task = client.post("/tasks", json={"title": "Buy oat milk"}).json()
    completed_task = client.post("/tasks", json={"title": "Buy almond milk"}).json()
    client.put(f"/tasks/{completed_task['id']}", json={"done": True})

    response = client.get("/tasks?search=milk&done=false")

    assert response.status_code == 200
    assert response.json() == [incomplete_task]


def test_get_tasks_is_sorted_alphabetically(client):
    client.post("/tasks", json={"title": "Zoo visit"})
    client.post("/tasks", json={"title": "apple pie"})

    titles = [task["title"] for task in client.get("/tasks").json()]

    assert titles == sorted(titles, key=str.casefold)


def test_stats_are_calculated_by_the_database(client):
    created_task = client.post("/tasks", json={"title": "Complete me"}).json()
    client.put(f"/tasks/{created_task['id']}", json={"done": True})

    response = client.get("/stats")

    assert response.status_code == 200
    assert response.json() == {"total": 4, "completed": 1, "incomplete": 3}


def test_stats_returns_zeroes_when_the_database_has_no_tasks(client):
    for task_id in (1, 2, 3):
        client.delete(f"/tasks/{task_id}")

    response = client.get("/stats")

    assert response.status_code == 200
    assert response.json() == {"total": 0, "completed": 0, "incomplete": 0}
