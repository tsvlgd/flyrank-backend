"""
Simple endpoint tests for the Task API.

Run the FastAPI server first:

    uv run uvicorn app.main:app --reload

Then run:

    uv run python test.py
"""

import requests

BASE_URL = "http://127.0.0.1:8000"


def check(name, response, expected_status):
    status = "PASS" if response.status_code == expected_status else "FAIL"

    print(f"\n[{status}] {name}")
    print(f"Expected: {expected_status}")
    print(f"Received: {response.status_code}")

    if response.content:
        try:
            print(response.json())
        except Exception:
            print(response.text)


def main():
    print("=" * 60)
    print("Testing Task API")
    print("=" * 60)

    # --------------------------------------------------
    # GET /
    # --------------------------------------------------
    response = requests.get(f"{BASE_URL}/")
    check("GET /", response, 200)

    # --------------------------------------------------
    # GET /health
    # --------------------------------------------------
    response = requests.get(f"{BASE_URL}/health")
    check("GET /health", response, 200)

    # --------------------------------------------------
    # GET /tasks
    # --------------------------------------------------
    response = requests.get(f"{BASE_URL}/tasks")
    check("GET /tasks", response, 200)

    # --------------------------------------------------
    # GET /tasks/{id}
    # --------------------------------------------------
    response = requests.get(f"{BASE_URL}/tasks/1")
    check("GET /tasks/1", response, 200)

    # --------------------------------------------------
    # GET invalid task
    # --------------------------------------------------
    response = requests.get(f"{BASE_URL}/tasks/999")
    check("GET /tasks/999", response, 404)

    # --------------------------------------------------
    # POST valid task
    # --------------------------------------------------
    response = requests.post(
        f"{BASE_URL}/tasks",
        json={"title": "Write tests"},
    )
    check("POST /tasks", response, 201)

    created_task = response.json()
    task_id = created_task["id"]

    # --------------------------------------------------
    # POST invalid task
    # --------------------------------------------------
    response = requests.post(
        f"{BASE_URL}/tasks",
        json={"title": ""},
    )
    check("POST empty title", response, 400)

    # --------------------------------------------------
    # PUT update title
    # --------------------------------------------------
    response = requests.put(
        f"{BASE_URL}/tasks/{task_id}",
        json={
            "title": "Updated title",
        },
    )
    check("PUT title only", response, 200)

    # --------------------------------------------------
    # PUT update done
    # --------------------------------------------------
    response = requests.put(
        f"{BASE_URL}/tasks/{task_id}",
        json={
            "done": True,
        },
    )
    check("PUT done only", response, 200)

    # --------------------------------------------------
    # PUT update both
    # --------------------------------------------------
    response = requests.put(
        f"{BASE_URL}/tasks/{task_id}",
        json={
            "title": "Completed task",
            "done": True,
        },
    )
    check("PUT title + done", response, 200)

    # --------------------------------------------------
    # PUT empty body
    # --------------------------------------------------
    response = requests.put(
        f"{BASE_URL}/tasks/{task_id}",
        json={},
    )
    check("PUT empty body", response, 400)

    # --------------------------------------------------
    # PUT invalid ID
    # --------------------------------------------------
    response = requests.put(
        f"{BASE_URL}/tasks/999",
        json={
            "title": "Doesn't exist",
        },
    )
    check("PUT invalid ID", response, 404)

    # --------------------------------------------------
    # DELETE task
    # --------------------------------------------------
    response = requests.delete(f"{BASE_URL}/tasks/{task_id}")
    check("DELETE /tasks/{id}", response, 204)

    # --------------------------------------------------
    # DELETE again
    # --------------------------------------------------
    response = requests.delete(f"{BASE_URL}/tasks/{task_id}")
    check("DELETE already deleted", response, 404)

    print("\n" + "=" * 60)
    print("Testing Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
