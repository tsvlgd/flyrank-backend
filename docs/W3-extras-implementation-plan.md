# Week 3 optional extras — implementation plan

## Goal

Extend the SQLite-backed Task API so the database, rather than Python loops,
performs task search, done-status filtering, alphabetical ordering, aggregate
statistics, and timestamp management.

The recommended implementation includes all five optional extras because they
work together naturally and demonstrate the main SQL ideas for this week.

## What changes for an API consumer

| Request | Database responsibility | Expected result |
|---|---|---|
| `GET /tasks` | retrieve rows | all tasks, alphabetically by title |
| `GET /tasks?search=milk` | `WHERE title LIKE ?` | tasks whose titles contain `milk` |
| `GET /tasks?done=true` | `WHERE done = ?` | only completed tasks |
| `GET /tasks?search=milk&done=false` | both conditions joined with `AND` | matching incomplete tasks |
| `GET /stats` | `COUNT(*)` queries | total, completed, and incomplete task counts |
| `POST /tasks` | insert timestamps | new task includes creation/update times |
| `PUT /tasks/{id}` | update `updated_at` | edited task has a newer update time |

## New concepts, in plain language

### Query parameters

The text after `?` in a URL is not part of the route path; it is a query
parameter. FastAPI turns a function parameter with a default value into an
optional query parameter:

```python
def get_tasks(search: str | None = None, done: bool | None = None):
    ...
```

For example, FastAPI converts `?done=true` into the Python value `True`. `None`
means the client did not send that filter, which is different from asking for
`done=false`.

### `LIKE` and wildcards

`LIKE` is SQL's pattern comparison operator. `%` means “zero or more
characters,” so the parameter `"%milk%"` matches `Buy milk` and `Milk the cat`.

```sql
SELECT * FROM tasks WHERE title LIKE ?;
```

Pass the pattern as a parameter, not by placing the user input directly inside
the SQL string:

```python
connection.execute(
    "SELECT * FROM tasks WHERE title LIKE ?",
    (f"%{search}%",),
)
```

The `?` placeholder keeps data separate from SQL instructions, which prevents
SQL injection. SQLite `LIKE` is usually case-insensitive for ordinary ASCII
text; do not promise case-sensitive behavior unless you intentionally configure
it.

### Building one query safely

The filters are optional, so start with the stable part of the query and add
only the requested conditions. SQL keywords and column names are developer
controlled; values remain `?` parameters.

```python
sql = "SELECT * FROM tasks"
conditions: list[str] = []
parameters: list[str | int] = []

if search is not None:
    conditions.append("title LIKE ?")
    parameters.append(f"%{search}%")
if done is not None:
    conditions.append("done = ?")
    parameters.append(int(done))

if conditions:
    sql += " WHERE " + " AND ".join(conditions)
sql += " ORDER BY title COLLATE NOCASE ASC"

rows = connection.execute(sql, parameters).fetchall()
```

`COLLATE NOCASE` is an intentional small refinement: it produces a friendlier
alphabetical order when titles begin with different ASCII letter cases. If the
assignment expects the literal `ORDER BY title`, use that instead.

### SQL aggregates

`COUNT(*)` asks SQLite to count rows. It returns one summary row rather than a
list of task rows, so it removes the need to fetch every task and count in
Python.

```sql
SELECT
    COUNT(*) AS total,
    SUM(CASE WHEN done = 1 THEN 1 ELSE 0 END) AS completed
FROM tasks;
```

Because `SUM` on an empty table can be `NULL`, make the response robust with
`COALESCE(..., 0)`, or use separate `COUNT(*)` queries.

### Schema versus data

A schema is the table's blueprint: its columns, types, and constraints. Adding
`created_at` and `updated_at` changes that blueprint, whereas inserting a task
only changes data within the existing blueprint.

For a fresh database, define the columns when creating `tasks`:

```sql
created_at TEXT NOT NULL,
updated_at TEXT NOT NULL
```

Use an ISO-8601 UTC string from Python, such as
`datetime.now(timezone.utc).isoformat()`. Text timestamps in this standard,
year-to-second order sort chronologically too.

```python
from datetime import datetime, timezone

now = datetime.now(timezone.utc).isoformat()
```

SQLite's `CREATE TABLE IF NOT EXISTS` does **not** add columns to a table that
already exists. Therefore a previously created `tasks.db` needs a deliberate
migration. For this learning project, the safe development approach is to:

1. Back up the existing database if its tasks matter.
2. Add each missing column using `ALTER TABLE tasks ADD COLUMN ...`.
3. Backfill existing rows with a known timestamp so `NOT NULL` expectations are
   met.
4. Verify the new schema with `PRAGMA table_info(tasks)`.

A more polished application records such changes as versioned migrations using
a migration tool. The README reflection should say that changing the table's
shape made the existing database a compatibility concern; migrations exist to
make those changes repeatable and safe across environments.

## Detailed implementation sequence

1. **Decide the response contract.** Add `created_at` and `updated_at` to the
   `Task` response model (as `datetime` values or ISO timestamp strings; choose
   one and use it consistently). Define a small `TaskStats` response model,
   for example `total`, `completed`, and `incomplete` integers.

2. **Make database initialization schema-aware.** Update the `CREATE TABLE`
   definition for new databases. Add a small, idempotent migration helper for
   existing databases: inspect `PRAGMA table_info(tasks)`, add absent columns,
   and backfill null/empty values. Run it before seed inserts. Do not delete the
   database automatically, because that would erase user data.

3. **Update seed data.** Seed rows must satisfy the timestamp columns. Generate
   a timestamp once for the seed operation or supply defaults at the database
   level. Keep the current “seed only when count is zero” behavior.

4. **Set timestamps during writes.** In `POST /tasks`, create one UTC timestamp
   and use it for both new fields. In `PUT /tasks/{task_id}`, generate a fresh
   UTC timestamp and include `updated_at = ?` in the `UPDATE`; preserve the
   original `created_at`.

5. **Enhance `GET /tasks`.** Add optional `search` and `done` function
   parameters. Assemble conditions and values as shown above, then add the
   fixed `ORDER BY title` clause. Execute exactly one filtered SQL query; do not
   fetch all rows and filter or sort them in Python.

6. **Add `GET /stats`.** Define this route before `GET /tasks/{task_id}` for
   clarity, although FastAPI's static `/stats` route does not conflict with the
   integer `task_id` path. Compute counts with `COUNT(*)`/`SUM(CASE...)` in SQL
   and return the result as JSON.

7. **Update documentation.** Add `/tasks` query examples and `/stats` to the
   endpoint table. Document timestamp fields and add the required two-sentence
   migration reflection. Include a short example:

   ```bash
   curl "http://127.0.0.1:8000/tasks?search=milk&done=false"
   curl http://127.0.0.1:8000/stats
   ```

8. **Extend automated tests.** Keep each test isolated through the existing
   temporary-database fixture. Test search, `done=true`, `done=false`, combined
   filters, alphabetical output, zero-task stats, stats after create/update,
   and timestamp behavior. For timestamps, assert they exist and that updating
   preserves `created_at` while changing `updated_at`; avoid brittle exact-time
   comparisons.

9. **Verify and commit.** Run `uv run pytest -v`, then manually inspect
   `/docs` and a few curl requests. If the work is complete, commit only the
   intended files with a message such as `Extras: search, filtering, stats, and
   timestamps`.

## Acceptance checklist

- [ ] Search and status filters are performed by SQL `WHERE` clauses.
- [ ] User-supplied values are always passed through `?` placeholders.
- [ ] `GET /tasks` is ordered by title in SQL.
- [ ] `GET /stats` obtains counts from SQL, including the empty-table case.
- [ ] New tasks receive both timestamps; updates change only `updated_at`.
- [ ] Existing local databases receive a safe, idempotent schema upgrade.
- [ ] Pydantic response models, README, and tests match the new API contract.
- [ ] All tests pass before the optional commit.

## Suggested commit

```text
Extras: search, filters, sorting, stats, and timestamps
```
