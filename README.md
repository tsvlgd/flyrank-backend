# Task API

A small, standalone REST API for managing tasks. It is built with FastAPI and
SQLite, with request validation, JSON error responses, persistent local storage,
and automated endpoint tests.

## Contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [Run locally](#run-locally)
- [API reference](#api-reference)
- [Database](#database)
- [Tests](#tests)
- [Project evidence](#project-evidence)
- [Stretch goals](#stretch-goals)

## Features

- Create, list, retrieve, update, and delete tasks
- Validate task titles and update payloads
- Return consistent JSON errors for invalid input, missing tasks, unknown routes,
  and unexpected server errors
- Store tasks in a local SQLite database that survives server restarts
- Seed a fresh database with example tasks
- Explore the API through Swagger UI
- Search, filter, sort, and summarize tasks with SQL
- Record task creation and update timestamps in UTC

## Tech stack

- Python 3.12
- FastAPI and Uvicorn
- Pydantic
- SQLite via Python's built-in `sqlite3` module
- Pytest and HTTPX for automated tests

## Run locally

```bash
uv sync
uv run uvicorn app.main:app --reload
```

The API is available at <http://127.0.0.1:8000>. Interactive documentation is
available at <http://127.0.0.1:8000/docs>.

On first startup, the application creates a local `tasks.db` file, creates the
`tasks` table, and seeds three example tasks. The database is intentionally
ignored by Git: it is runtime data, and every clone can generate its own clean
copy.

If a database was created before timestamps were added, startup safely adds the
missing `created_at` and `updated_at` columns and backfills existing tasks. It
does not delete or reseed existing tasks.

## API reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | API metadata |
| `GET` | `/health` | Health check |
| `GET` | `/stats` | Return total, completed, and incomplete task counts |
| `GET` | `/tasks` | List tasks; supports `search` and `done` query filters |
| `GET` | `/tasks/{task_id}` | Get a task by ID |
| `POST` | `/tasks` | Create a task |
| `PUT` | `/tasks/{task_id}` | Update a task title, completion state, or both |
| `DELETE` | `/tasks/{task_id}` | Delete a task |

Task responses include `created_at` and `updated_at` as ISO-8601 UTC strings.

Create a task:

```bash
curl -X POST http://127.0.0.1:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"title":"Learn FastAPI"}'
```

Example response:

```json
{
  "id": 4,
  "title": "Learn FastAPI",
  "done": false,
  "created_at": "2026-09-17T10:00:00+00:00",
  "updated_at": "2026-09-17T10:00:00+00:00"
}
```

Search incomplete tasks and view database-calculated statistics:

```bash
curl "http://127.0.0.1:8000/tasks?search=milk&done=false"
curl http://127.0.0.1:8000/stats
```

## Database

SQLite keeps the entire database in one local file and needs no separate
database server. You can inspect `tasks.db` in DB Browser for SQLite while the
API is running; changes made there are visible through `GET /tasks` because
both tools use the same file.

For example, list completed tasks with:

```sql
SELECT * FROM tasks WHERE done = 1;
```

## Tests

Run the automated test suite:

```bash
uv run pytest -v
```

Each test uses its own temporary SQLite file, so tests never modify your local
`tasks.db`. A lightweight manual smoke-test script is also available after the
server starts:

```bash
uv run python tests/test.py
```

### Latest automated verification

```text
$ uv run pytest tests/
======================== 17 passed, 1 warning in 1.56s ========================
```

All CRUD, persistence, timestamp migration, search, filtering, sorting, and
statistics checks passed. The warning is emitted by the current FastAPI test
client dependency and does not affect the passing test result.

## Project evidence

Swagger UI:

![Swagger UI](docs/swagger-ui.png)

SQLite table inspection:

![Task table](docs/task-table.png)

Manual SQL query execution:

![Manual query execution](docs/manual-query-execution.png)

CRUD API logs:

![CRUD API logs](docs/API-logs.png)

## Stretch goals

Implemented extras use SQL rather than Python loops:

- `GET /tasks?search=milk` searches task titles with `LIKE`.
- `GET /tasks?done=true` or `?done=false` filters by completion state.
- `GET /tasks` orders titles alphabetically with `ORDER BY`.
- `GET /stats` calculates counts with `COUNT` and `SUM`.
- New tasks receive `created_at` and `updated_at`; updates change only
  `updated_at`.

Timestamp support demonstrates a small idempotent migration: startup checks for
missing columns, adds them, and backfills existing rows once. Changing a table's
shape makes existing database files a compatibility concern; migrations make
those changes repeatable and safe across environments.
