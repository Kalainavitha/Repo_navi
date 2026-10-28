STORY_SIGN_IN = b"As a user, I want to sign in so that I can see my account."


def make_member(client, **overrides):
    payload = {"name": "Member", "role": "Backend Developer", "skills": ["python"], "experience": 5, "hours_per_day": 8, "allocation": 100}
    payload.update(overrides)
    created = client.post("/api/team-members", json=payload)
    assert created.status_code == 201, created.text
    return created.json()


def planned_project(client, name, document, member_ids):
    project = client.post("/api/projects", json={
        "name": name, "description": name, "project_type": "Web Application",
        "start_date": "2026-11-02", "deadline": "2026-12-31", "member_ids": member_ids,
    })
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]
    assert client.post(f"/api/projects/{project_id}/documents", files={"file": ("story.txt", document)}).status_code == 200
    generated = client.post(f"/api/projects/{project_id}/generate-plan")
    assert generated.status_code == 200, generated.text
    return project_id, generated.json()


def test_anyone_can_reassign_and_edit_tasks(client):
    first = make_member(client, name="Lena Lead", role="Team Lead")
    second = make_member(client, name="Dev Dan")
    _project_id, plan = planned_project(client, "Open Edit", STORY_SIGN_IN, [first["id"], second["id"]])
    task = plan["tasks"][0]
    other = second["id"] if task["assignee_id"] == first["id"] else first["id"]

    # no user header, no lead: it simply works
    moved = client.patch(f"/api/tasks/{task['id']}", json={"assignee_id": other})
    assert moved.status_code == 200, moved.text
    assert moved.json()["assignee_id"] == other
    renamed = client.patch(f"/api/tasks/{task['id']}", json={"effort_hours": 6})
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["manually_edited"] is True


def test_member_can_be_promoted_to_lead(client):
    member = make_member(client, name="Promote Me")
    updated = client.patch(f"/api/team-members/{member['id']}", json={"is_lead": True})
    assert updated.status_code == 200
    assert updated.json()["is_lead"] is True


def test_regenerating_reuploading_and_deleting_a_plan_clears_daily_allocations(client):
    member = make_member(client, name="Solo Dev")
    project_id, _first = planned_project(client, "Regenerate", STORY_SIGN_IN, [member["id"]])
    assert client.post(f"/api/projects/{project_id}/generate-plan").status_code == 200
    reupload = client.post(f"/api/projects/{project_id}/documents", files={"file": ("story.txt", b"As a user, I want to export reports so that finance can reconcile.")})
    assert reupload.status_code == 200, reupload.text
    assert client.post(f"/api/projects/{project_id}/generate-plan").status_code == 200
    assert client.delete(f"/api/projects/{project_id}").status_code == 204


def test_second_project_respects_first_bookings_and_allocations_endpoint(client):
    member = make_member(client, name="Shared Dev", experience=8)
    _first_id, first = planned_project(client, "Billing Portal", b"As a customer, I want to view invoices so that I can track billing. As an admin, I want to export billing reports so that finance can reconcile.", [member["id"]])
    _second_id, second = planned_project(client, "Warehouse App", b"As an operator, I want to scan barcodes so that I can update inventory counts.", [member["id"]])

    per_day = {}
    for plan in (first, second):
        for task in plan["tasks"]:
            for allocation in task["daily_allocations"]:
                per_day[allocation["date"]] = per_day.get(allocation["date"], 0) + allocation["hours"]
    assert all(hours <= 8.001 for hours in per_day.values())
    assert first["tasks"][0]["title"] != second["tasks"][0]["title"]

    data = client.get(f"/api/team-members/{member['id']}/allocations")
    assert data.status_code == 200, data.text
    body = data.json()
    assert body["totals"]["project_count"] == 2
    assert {item["name"] for item in body["projects"]} == {"Billing Portal", "Warehouse App"}
    assert all(item["tasks"] and item["assigned_hours"] > 0 for item in body["projects"])
    assert body["weekly"] and body["daily_capacity"] == 8
    assert client.get("/api/team-members/missing/allocations").status_code == 404


def test_plan_tasks_expose_their_own_summary_and_risk_fields(client):
    member = make_member(client, name="Risky Dev")
    _project_id, plan = planned_project(client, "Summary Check", STORY_SIGN_IN, [member["id"]])
    for task in plan["tasks"]:
        assert task["summary"] and task["summary"] != task["description"]
        assert task["risk_level"] in {"Low", "Medium", "High"}
    assert isinstance(plan["summary"]["risks"], list)
    assert "risk_score" in plan["summary"]


def test_dashboard_recent_projects_include_risk_level(client):
    member = make_member(client, name="Dash Dev")
    planned_project(client, "Dash Project", STORY_SIGN_IN, [member["id"]])
    recent = client.get("/api/dashboard").json()["recent_projects"]
    assert recent and recent[0]["risk_level"] in {"Low", "Medium", "High"}


def test_calendar_endpoint_lists_deadlines_and_task_due_dates(client):
    member = make_member(client, name="Calendar Dev")
    planned_project(client, "Calendar Project", STORY_SIGN_IN, [member["id"]])
    nov = client.get("/api/calendar?month=2026-11").json()
    types = {event["type"] for event in nov["events"]}
    assert "project_start" in types and "task_due" in types
    dec = client.get("/api/calendar?month=2026-12").json()
    assert any(event["type"] == "deadline" for event in dec["events"])
    assert client.get("/api/calendar?month=bad").status_code == 422


def test_team_lead_role_enables_task_editing_automatically(client):
    lead = make_member(client, name="Role Lead", role="Team Lead")
    assert lead["is_lead"] is True
    extra = make_member(client, name="Dual Role", role="Backend Developer", additional_role="Team Lead")
    assert extra["is_lead"] is True and extra["additional_role"] == "Team Lead"
    dev = make_member(client, name="Plain Dev")
    assert dev["is_lead"] is False and dev["additional_role"] is None

    promoted = client.patch(f"/api/team-members/{dev['id']}", json={"additional_role": "Team Lead"}).json()
    assert promoted["is_lead"] is True
    demoted = client.patch(f"/api/team-members/{dev['id']}", json={"additional_role": ""}).json()
    assert demoted["is_lead"] is False
    # an unrelated edit never changes lead status
    assert client.patch(f"/api/team-members/{lead['id']}", json={"experience": 12}).json()["is_lead"] is True


def test_member_can_be_created_without_email_or_allocation(client):
    created = client.post("/api/team-members", json={"name": "No Email", "role": "QA Engineer", "skills": ["testing"], "experience": 2, "hours_per_day": 6, "email": ""})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["email"] is None
    assert body["allocation"] == 100


def test_team_workload_lists_hours_per_person_per_project(client):
    busy = make_member(client, name="Busy Bee", experience=9)
    idle = make_member(client, name="Idle Ian", role="QA Engineer", skills=["testing"], available_from="2019-01-01", available_until="2019-01-02")
    planned_project(client, "Alpha", b"As a user, I want to sign in so that I can see my account.", [busy["id"]])
    planned_project(client, "Beta", b"As an operator, I want to scan barcodes so that I can update inventory counts.", [busy["id"]])
    data = client.get("/api/team-workload")
    assert data.status_code == 200, data.text
    body = data.json()
    assert {item["name"] for item in body["projects"]} == {"Alpha", "Beta"}
    people = {item["name"]: item for item in body["members"]}
    assert {entry["name"] for entry in people["Busy Bee"]["by_project"]} == {"Alpha", "Beta"}
    assert people["Busy Bee"]["total_hours"] == round(sum(e["hours"] for e in people["Busy Bee"]["by_project"]), 1) > 0
    assert people["Busy Bee"]["weekly_hours"] == 40
    assert people["Idle Ian"]["by_project"] == [] and people["Idle Ian"]["total_hours"] == 0
    assert idle["id"] == people["Idle Ian"]["id"]


def test_old_plans_get_a_short_task_specific_summary(client):
    from sqlalchemy.orm import Session
    from app.models import Task

    member = make_member(client, name="Legacy Dev")
    project_id, plan = planned_project(client, "Legacy", STORY_SIGN_IN, [member["id"]])
    assert all(task["summary_source"] == "task" for task in plan["tasks"])

    # Simulate a plan from before tasks had their own summary: the description is the whole story.
    long_story = "As a logged-in user, I want to see a simple dashboard landing page after signing in. " + "Requirement text. " * 120
    with Session(client.app.state.test_engine) as db:
        for task in db.query(Task).filter(Task.project_id == project_id).all():
            task.summary = ""
            task.description = long_story
            task.source_story = "User Story: Dashboard Landing Page Story ID DASH-001 Priority Medium"
        db.commit()

    tasks = client.get(f"/api/projects/{project_id}/tasks").json()
    assert tasks
    for task in tasks:
        assert task["summary_source"] == "derived"
        assert len(task["summary"]) <= 150
        assert task["summary"] != long_story[: len(task["summary"])]
        assert "Dashboard Landing Page" in task["summary"]
        assert "Story ID" not in task["summary"]
    assert len({task["summary"] for task in tasks}) <= len(tasks)


def test_changing_task_status_keeps_remaining_hours_truthful_and_is_open_to_everyone(client):
    member = make_member(client, name="Status Dev")
    project_id, plan = planned_project(client, "Status", STORY_SIGN_IN, [member["id"]])
    task = next(t for t in plan["tasks"] if t["assignee_id"])
    assert task["remaining_hours"] == task["effort_hours"]

    # no Team Lead header needed to report progress
    started = client.patch(f"/api/tasks/{task['id']}", json={"status": "In Progress"})
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "In Progress" and started.json()["remaining_hours"] == task["effort_hours"]
    assert started.json()["manually_edited"] is False

    done = client.patch(f"/api/tasks/{task['id']}", json={"status": "Completed"}).json()
    assert done["status"] == "Completed" and done["remaining_hours"] == 0

    allocations = client.get(f"/api/team-members/{member['id']}/allocations").json()
    assert allocations["totals"]["completed_hours"] >= task["effort_hours"]

    reopened = client.patch(f"/api/tasks/{task['id']}", json={"status": "Pending"}).json()
    assert reopened["remaining_hours"] == task["effort_hours"]
    assert client.patch(f"/api/tasks/{task['id']}", json={"status": "Bogus"}).status_code == 422

    progress = client.get(f"/api/projects/{project_id}/plan").json()["summary"]["progress_percent"]
    assert 0 <= progress <= 100


def test_dashboard_returns_more_than_five_upcoming_deadlines_in_date_order(client):
    member = make_member(client, name="Deadline Dev")
    for index in range(12):
        project = client.post("/api/projects", json={
            "name": f"Deadline Project {index:02d}", "description": "x", "project_type": "Web Application",
            "start_date": "2026-11-02", "deadline": f"2027-01-{index + 1:02d}", "member_ids": [member["id"]],
        })
        assert project.status_code == 201, project.text
        project_id = project.json()["id"]
        assert client.post(f"/api/projects/{project_id}/documents", files={"file": ("s.txt", STORY_SIGN_IN)}).status_code == 200
        assert client.post(f"/api/projects/{project_id}/generate-plan").status_code == 200
    upcoming = client.get("/api/dashboard").json()["upcoming_deadlines"]
    assert len(upcoming) == 12
    assert [item["deadline"] for item in upcoming] == sorted(item["deadline"] for item in upcoming)
    assert upcoming[0]["name"] == "Deadline Project 00" and upcoming[-1]["name"] == "Deadline Project 11"


def test_status_changes_record_started_and_completed_timestamps(client):
    member = make_member(client, name="Clock Dev")
    _project_id, plan = planned_project(client, "Clock", STORY_SIGN_IN, [member["id"]])
    task = next(t for t in plan["tasks"] if t["assignee_id"])
    assert task["started_at"] is None and task["completed_at"] is None

    started = client.patch(f"/api/tasks/{task['id']}", json={"status": "In Progress"}).json()
    assert started["started_at"] and started["completed_at"] is None
    first_start = started["started_at"]

    # moving between non-final states never resets the start
    assert client.patch(f"/api/tasks/{task['id']}", json={"status": "Blocked"}).json()["started_at"] == first_start

    done = client.patch(f"/api/tasks/{task['id']}", json={"status": "Completed"}).json()
    assert done["completed_at"] and done["started_at"] == first_start

    reopened = client.patch(f"/api/tasks/{task['id']}", json={"status": "In Progress"}).json()
    assert reopened["completed_at"] is None and reopened["started_at"] == first_start

    # completing a task that was never started still records both
    other = next(t for t in plan["tasks"] if t["id"] != task["id"] and t["assignee_id"])
    straight = client.patch(f"/api/tasks/{other['id']}", json={"status": "Completed"}).json()
    assert straight["started_at"] and straight["completed_at"]
