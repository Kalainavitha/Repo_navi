"""A person who joins the team after projects exist must show up in them and be given unstarted work."""
from collections import defaultdict
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.models import TeamMember
from tests.test_replan import DOC, make_member, make_plan

TODAY = "2026-11-12"


class FrozenDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 11, 2)


@pytest.fixture
def frozen_today(monkeypatch):
    """Auto-assignment on member creation uses the real 'today'; pin it so the tests stay valid as time passes."""
    monkeypatch.setattr("app.main.date", FrozenDate)


def project_tasks(client, project_id):
    return {t["id"]: t for t in client.get(f"/api/projects/{project_id}/tasks").json()}


def team_of(client, project_id):
    return {m["name"] for m in client.get(f"/api/projects/{project_id}/team-members").json()}


def second_project(client, members, name="Second"):
    project = client.post("/api/projects", json={
        "name": name, "description": "x", "project_type": "Web Application",
        "start_date": "2026-11-02", "deadline": "2026-12-18", "member_ids": [m["id"] for m in members],
    })
    project_id = project.json()["id"]
    client.post(f"/api/projects/{project_id}/documents", files={"file": ("s.txt", DOC)})
    assert client.post(f"/api/projects/{project_id}/generate-plan").status_code == 200
    return project_id


def per_day_hours(client, project_ids):
    hours = defaultdict(float)
    for project_id in project_ids:
        for task in project_tasks(client, project_id).values():
            for allocation in task["daily_allocations"]:
                hours[(task["assignee_id"], allocation["date"])] += allocation["hours"]
    return hours


def test_a_new_member_joins_every_active_project_and_gets_unstarted_work(client, frozen_today):
    ana = make_member(client, name="Ana", role="Backend Developer", skills=["python"], experience=8)
    first, _plan = make_plan(client, [ana])
    other = second_project(client, [ana])
    assert team_of(client, first) == {"Ana"} and team_of(client, other) == {"Ana"}

    nancy = client.post("/api/team-members", json={
        "name": "Nancy", "role": "Backend Developer", "skills": ["python"], "experience": 5, "hours_per_day": 8,
    })
    assert nancy.status_code == 201, nancy.text
    nancy_id = nancy.json()["id"]

    for project_id in (first, other):
        assert team_of(client, project_id) == {"Ana", "Nancy"}   # she is now on both projects
    given = [t for pid in (first, other) for t in project_tasks(client, pid).values() if t["assignee_id"] == nancy_id]
    assert given, "a qualified newcomer must be handed some of the unstarted work"
    assert all(t["status"] == "Pending" for t in given)
    assert all("joined the project" in (t["rationale"] or "") for t in given)

    # she shows up in the team chart and the allocations view with real hours
    chart = {m["name"]: m for m in client.get("/api/team-workload").json()["members"]}
    assert chart["Nancy"]["total_hours"] > 0
    assert client.get(f"/api/team-members/{nancy_id}/allocations").json()["totals"]["task_count"] == len(given)
    # nobody is over capacity, even across both projects
    assert all(hours <= 8.01 for hours in per_day_hours(client, (first, other)).values())


def test_started_and_finished_work_never_moves_to_the_newcomer(client, frozen_today):
    ana = make_member(client, name="Ana", role="Backend Developer", skills=["python"], experience=8)
    project_id, plan = make_plan(client, [ana])
    started, finished, halted = plan["tasks"][0], plan["tasks"][1], plan["tasks"][2]
    client.patch(f"/api/tasks/{started['id']}", json={"status": "In Progress"})
    client.patch(f"/api/tasks/{finished['id']}", json={"status": "Completed"})
    client.patch(f"/api/tasks/{halted['id']}", json={"status": "Blocked"})
    before = project_tasks(client, project_id)

    client.post("/api/team-members", json={"name": "Nancy", "role": "Backend Developer", "skills": ["python"], "experience": 5, "hours_per_day": 8})
    after = project_tasks(client, project_id)
    for task in (started, finished, halted):
        assert after[task["id"]]["assignee_id"] == ana["id"]
        assert (after[task["id"]]["start_date"], after[task["id"]]["end_date"], after[task["id"]]["status"]) == \
               (before[task["id"]]["start_date"], before[task["id"]]["end_date"], before[task["id"]]["status"])
        assert after[task["id"]]["daily_allocations"] == before[task["id"]]["daily_allocations"]


def test_an_unqualified_newcomer_joins_but_takes_nothing(client, frozen_today):
    ana = make_member(client, name="Ana", role="Backend Developer", skills=["python", "react"], experience=8)
    project_id, _plan = make_plan(client, [ana])
    before = {k: v["assignee_id"] for k, v in project_tasks(client, project_id).items()}
    client.post("/api/team-members", json={"name": "Away Alex", "role": "Backend Developer", "skills": ["python"], "experience": 5,
                                           "hours_per_day": 8, "available_from": "2019-01-01", "available_until": "2019-01-02"})
    assert team_of(client, project_id) == {"Ana", "Away Alex"}      # still listed on the project
    assert {k: v["assignee_id"] for k, v in project_tasks(client, project_id).items()} == before


def test_archived_projects_are_left_alone(client, frozen_today):
    ana = make_member(client, name="Ana", role="Backend Developer", skills=["python"], experience=8)
    project_id, _plan = make_plan(client, [ana])
    client.post(f"/api/projects/{project_id}/archive")
    client.post("/api/team-members", json={"name": "Nancy", "role": "Backend Developer", "skills": ["python"], "experience": 5, "hours_per_day": 8})
    assert team_of(client, project_id) == {"Ana"}
    assert client.post(f"/api/projects/{project_id}/rebalance").status_code == 409


def test_members_added_before_this_feature_can_be_brought_in_with_the_button(client):
    """The case from real data: people were added to the team after the plans were made, with no auto-join."""
    ana = make_member(client, name="Ana", role="Backend Developer", skills=["python"], experience=8)
    project_id, _plan = make_plan(client, [ana])
    with Session(client.app.state.test_engine) as db:   # inserted directly, so nothing joined them automatically
        db.add(TeamMember(id="late-1", name="Late Lia", role="Backend Developer", skills=["python"], experience=5, hours_per_day=8, allocation=100,
                          working_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], leave_dates=[], is_lead=False))
        db.commit()
    assert team_of(client, project_id) == {"Ana"}

    result = client.post(f"/api/projects/{project_id}/rebalance", params={"today": "2026-11-02"})
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["added_members"] == ["Late Lia"]
    assert body["moved"] and all(item["to"] == "Late Lia" and item["from"] == "Ana" for item in body["moved"])
    assert team_of(client, project_id) == {"Ana", "Late Lia"}
    assert any(t["assignee_id"] == "late-1" for t in project_tasks(client, project_id).values())

    again = client.post(f"/api/projects/{project_id}/rebalance", params={"today": "2026-11-02"}).json()
    assert again["added_members"] == [] and again["moved"] == []   # second press changes nothing


def test_rebalanced_plans_keep_dependencies_and_capacity_rules(client):
    ana = make_member(client, name="Ana", role="Backend Developer", skills=["python", "react"], experience=8)
    project_id, _plan = make_plan(client, [ana])
    with Session(client.app.state.test_engine) as db:
        db.add(TeamMember(id="late-2", name="Late Leo", role="Frontend Developer", skills=["react"], experience=3, hours_per_day=6, allocation=100,
                          working_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], leave_dates=["2026-11-04"], is_lead=False))
        db.commit()
    client.post(f"/api/projects/{project_id}/rebalance", params={"today": "2026-11-02"})
    tasks = project_tasks(client, project_id)
    for task in tasks.values():
        assert abs(sum(a["hours"] for a in task["daily_allocations"]) - task["effort_hours"]) < 0.05
        for dependency in task["dependencies"]:
            assert task["start_date"] > tasks[dependency]["end_date"], f"{task['id']} starts before {dependency} ends"
    hours = per_day_hours(client, [project_id])
    assert all(h <= 8.01 for (member, _day), h in hours.items() if member != "late-2")
    assert all(h <= 6.01 for (member, _day), h in hours.items() if member == "late-2")
    assert all(day != "2026-11-04" for (member, day) in hours if member == "late-2")  # his leave day is respected


def test_regenerating_a_plan_uses_the_whole_team_as_it_is_now(client):
    ana = make_member(client, name="Ana", role="Backend Developer", skills=["python", "react"], experience=8)
    project_id, _plan = make_plan(client, [ana])
    with Session(client.app.state.test_engine) as db:
        db.add(TeamMember(id="late-3", name="Late Lou", role="Backend Developer", skills=["python", "react"], experience=6, hours_per_day=8, allocation=100,
                          working_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], leave_dates=[], is_lead=False))
        db.commit()
    assert team_of(client, project_id) == {"Ana"}
    regenerated = client.post(f"/api/projects/{project_id}/generate-plan")
    assert regenerated.status_code == 200, regenerated.text
    assert team_of(client, project_id) == {"Ana", "Late Lou"}
    assert {t["assignee_name"] for t in regenerated.json()["tasks"]} <= {"Ana", "Late Lou"}
