# Task API

A small, robust REST API for managing tasks. It is built with FastAPI, PostgreSQL, Redis, Alembic, and Docker Compose, featuring asynchronous endpoints, connection pooling, request validation, persistent storage, and automated integration tests.

## Contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [Run locally (Docker)](#run-locally)
- [API reference](#api-reference)
- [Database](#database)
- [Tests](#tests)

## Features

- **Asynchronous Architecture**: Fully async route handlers (`async/await`) and database interactions for high concurrency.
- **Connection Pooling**: Reuses active database connections via `psycopg_pool`.
- **Database Migrations**: Automated schema versioning and deployment using Alembic.
- **Redis Healthcheck**: Incorporates Redis alongside Postgres in a `/health` readiness probe.
- Create, list, retrieve, update, and delete tasks.
- Validate task titles and update payloads.
- Search, filter, sort, and summarize tasks with SQL.
- Prevent duplicate data natively via `UNIQUE` constraints (`ON CONFLICT`).

## Tech stack

- Python 3.12
- FastAPI and Uvicorn
- Pydantic
- PostgreSQL 18 & `psycopg` (async)
- Redis 7
- Alembic
- Docker & Docker Compose
- Pytest and HTTPX for automated tests

## Run locally

The easiest way to run the entire stack is with Docker Compose:

```bash
docker compose up --build -d
```

The API is available at <http://127.0.0.1:8000>. Interactive documentation is
available at <http://127.0.0.1:8000/docs>.

On startup, Docker Compose will launch PostgreSQL and Redis containers, and the API container will run Alembic migrations automatically before booting the server and seeding the database. 

## API reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | API metadata |
| `GET` | `/health` | Health check (Checks Postgres and Redis) |
| `GET` | `/stats` | Return total, completed, and incomplete task counts |
| `GET` | `/tasks` | List tasks; supports `search` and `done` query filters |
| `GET` | `/tasks/{task_id}` | Get a task by ID |
| `POST` | `/tasks` | Create a task |
| `PUT` | `/tasks/{task_id}` | Update a task title, completion state, or both |
| `DELETE` | `/tasks/{task_id}` | Delete a task |

## Tests

Run the automated test suite locally:

```bash
uv run pytest -v
```

Automated tests use the separate PostgreSQL database named `tasks_test`. Before each test session, pytest triggers Alembic programmatically to ensure the schema is up-to-date, and truncates all rows before each individual test for a clean slate.

### Latest automated verification

```text
$ uv run pytest
======================= 13 passed, 14 warnings in 9.14s ========================
```

## Next Week's Goals & Assignment Checklist

**Goal & purpose**: Build a secure API that handles user authentication — Sign Up, Log In, Log Out — and protects specific routes so they answer only for logged-in users. We will use Supabase Auth as the Identity Provider (IdP) to manage accounts, issue JSON Web Tokens (JWTs), verify those tokens to guard "user-only" endpoints, document the flow in Swagger UI, and publish everything to GitHub. 

We will avoid rolling our own cryptography and instead lean on a trusted IdP. Supabase stores the accounts, hashes the passwords, and signs the tokens; our job is receiving a token, verifying it, and opening (or refusing) the door.

### Task Checklist
- [ ] **Setup Supabase Auth**: Configure Supabase as our Identity Provider.
- [ ] **JWT Verification**: Implement FastAPI dependency to verify incoming Supabase JWTs.
- [ ] **Protect Endpoints**: Guard specific routes so they are only accessible to authenticated users.
- [ ] **Redis Rate Limiting**: Utilize our new Redis integration to build a robust rate limiter for our endpoints.
- [ ] **Swagger UI Auth Integration**: Update FastAPI Swagger UI to accept Bearer tokens for easy testing.
- [ ] **GitHub Publish**: Push the authenticated API up to GitHub.

### Why an Identity Provider (IdP) instead of Manual Auth?
* **The Danger of Manual Auth:** Building auth from scratch means writing your own cryptography, password hashing, and reset flows. A single mistake can compromise all user data.
* **Separation of Concerns:** A backend API should focus on business logic (managing tasks). Offloading auth to an IdP keeps the codebase clean and focused.
* **The "VIP Pass" Flow:** 
  1. The user authenticates directly with the IdP (e.g., Supabase).
  2. The IdP issues a cryptographically signed JSON Web Token (JWT).
  3. The user passes this JWT to our FastAPI backend.
  4. Our backend mathematically verifies the signature and grants access, all without ever seeing the user's password.
