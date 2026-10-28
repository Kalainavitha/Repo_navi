"""Delay impact and Re-plan from today."""
from collections import defaultdict

DOC = (
    b"As a customer, I want to sign in with email and password so that I can access my account securely. "
    b"As a customer, I want to view my invoice history on a dashboard so that I can track billing. "
    b"As an admin, I want to export billing reports to CSV so that finance can reconcile payments."
)
TODAY = "2026-11-12"


def make_member(client, **overrides):
    payload = {"name": "Member", "role": "Backend Developer", "skills": ["python", "react"], "experience": 6, "hours_per_day": 8}
    payload.update(overrides)
    created = client.post("/api/team-members", json=payload)
    assert created.status_code == 201, created.text
    return created.json()


def make_plan(client, members):
    project = client.post("/api/projects", json={
        "name": "Replan", "description": "x", "project_type": "Web Application",
        "start_date": "2026-11-02", "deadline": "2026-12-18", "member_ids": [m["id"] for m in members],
    })
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]
    assert client.post(f"/api/projects/{project_id}/documents", files={"file": ("s.txt", DOC)}).status_code == 200
    generated = client.post(f"/api/projects/{project_id}/generate-plan")
    assert generated.status_code == 200, generated.text
    return project_id, generated.json()


def snapshot(client, project_id):
    return {t["id"]: t for t in client.get(f"/api/projects/{project_id}/tasks").json()}


def test_impact_is_read_only_and_reports_overdue_and_halted_work(client):
    members = [make_member(client, name="Ana"), make_member(client, name="Bo", experience=3)]
    project_id, plan = make_plan(client, members)
    tasks = plan["tasks"]
    before = snapshot(client, project_id)

    client.patch(f"/api/tasks/{tasks[0]['id']}", json={"status": "Completed"})
    blocked = next(t for t in tasks if t["status"] == "Pending" and t["assignee_id"] and t["id"] != tasks[0]["id"])
    client.patch(f"/api/tasks/{blocked['id']}", json={"status": "Blocked"})

    impact = client.get(f"/api/projects/{project_id}/impact", params={"today": TODAY})
    assert impact.status_code == 200, impact.text
    body = impact.json()
    assert body["today"] == TODAY
    assert [item["id"] for item in body["blocked"]] == [blocked["id"]]
    assert all(item["end_date"] < TODAY for item in body["overdue"])
    assert body["overdue"], "tasks planned before today and not completed must be reported as overdue"
    assert body["needs_replan"] is True
    assert body["replanned_finish"] >= TODAY
    assert body["slip_days"] == (
        __import__("datetime").date.fromisoformat(body["replanned_finish"]) - __import__("datetime").date.fromisoformat(body["original_finish"])
    ).days
    assert body["people_affected"]

    after = snapshot(client, project_id)
    for task_id, task in before.items():
        if task_id != tasks[0]["id"] and task_id != blocked["id"]:
            assert (after[task_id]["start_date"], after[task_id]["end_date"]) == (task["start_date"], task["end_date"])


def test_replan_moves_only_unfinished_work_to_today_or_later_without_breaking_rules(client):
    members = [make_member(client, name="Ana"), make_member(client, name="Bo", experience=3, skills=["react", "python"])]
    project_id, plan = make_plan(client, members)
    done_ids = [t["id"] for t in plan["tasks"][:2]]
    for task_id in done_ids:
        client.patch(f"/api/tasks/{task_id}", json={"status": "Completed"})
    before = snapshot(client, project_id)

    saved = client.post(f"/api/projects/{project_id}/replan", params={"today": TODAY})
    assert saved.status_code == 200, saved.text
    after = snapshot(client, project_id)

    for task_id in done_ids:  # history is untouched
        assert (after[task_id]["start_date"], after[task_id]["end_date"], after[task_id]["status"]) == (before[task_id]["start_date"], before[task_id]["end_date"], "Completed")
        assert after[task_id]["daily_allocations"] == before[task_id]["daily_allocations"]

    for task_id, task in after.items():
        assert task["assignee_id"] == before[task_id]["assignee_id"]  # nobody is reassigned
        if task_id in done_ids or not task["assignee_id"]:
            continue
        assert task["start_date"] >= TODAY, task_id
        assert abs(sum(a["hours"] for a in task["daily_allocations"]) - task["remaining_hours"]) < 0.05
        assert all(a["date"] >= TODAY for a in task["daily_allocations"])
        for dependency in task["dependencies"]:
            if dependency not in done_ids:
                assert task["start_date"] > after[dependency]["end_date"], f"{task_id} starts before {dependency} ends"

    per_day = defaultdict(float)
    for task in after.values():
        for a in task["daily_allocations"]:
            if task["id"] not in done_ids:
                per_day[(task["assignee_id"], a["date"])] += a["hours"]
    assert all(hours <= 8.01 for hours in per_day.values())

    # the stored summary follows the new finish date
    plan_after = client.get(f"/api/projects/{project_id}/plan").json()
    latest = max(t["end_date"] for t in after.values() if t["end_date"])
    assert plan_after["summary"]["projected_completion"] == latest


def test_replan_flags_halted_tasks_and_a_second_replan_changes_nothing(client):
    members = [make_member(client, name="Ana")]
    project_id, plan = make_plan(client, members)
    halted = plan["tasks"][2]
    client.patch(f"/api/tasks/{halted['id']}", json={"status": "Blocked"})

    first = client.post(f"/api/projects/{project_id}/replan", params={"today": TODAY})
    assert first.status_code == 200
    state = snapshot(client, project_id)
    assert "blocker" in (state[halted["id"]]["warning"] or "").lower()
    assert state[halted["id"]]["status"] == "Blocked"

    client.post(f"/api/projects/{project_id}/replan", params={"today": TODAY})
    again = snapshot(client, project_id)
    assert {k: (v["start_date"], v["end_date"]) for k, v in again.items()} == {k: (v["start_date"], v["end_date"]) for k, v in state.items()}


def test_replan_rejects_archived_projects_and_bad_dates(client):
    members = [make_member(client, name="Ana")]
    project_id, _plan = make_plan(client, members)
    assert client.get(f"/api/projects/{project_id}/impact", params={"today": "not-a-date"}).status_code == 422
    assert client.get("/api/projects/9999/impact").status_code == 404
    client.post(f"/api/projects/{project_id}/archive")
    assert client.post(f"/api/projects/{project_id}/replan", params={"today": TODAY}).status_code == 409


def test_a_plan_that_is_on_schedule_needs_no_replan(client):
    members = [make_member(client, name="Ana"), make_member(client, name="Bo", experience=3)]
    project_id, _plan = make_plan(client, members)
    body = client.get(f"/api/projects/{project_id}/impact", params={"today": "2026-11-02"}).json()
    assert body["overdue"] == [] and body["blocked"] == []
    assert body["slip_days"] <= 0
    assert body["needs_replan"] is False


def test_moving_earlier_is_not_a_delay(client):
    """Re-planning from before the project even starts can only pull work earlier; that must not look like a problem."""
    members = [make_member(client, name="Ana"), make_member(client, name="Bo", experience=3)]
    project_id, _plan = make_plan(client, members)
    body = client.get(f"/api/projects/{project_id}/impact", params={"today": "2026-10-01"}).json()
    assert all(task["delta_days"] <= 0 for task in body["shifted_tasks"])
    assert body["needs_replan"] is False
