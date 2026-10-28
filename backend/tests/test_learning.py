"""Estimate Coach: planned vs actual duration becomes a per-person correction for new plans."""
from datetime import date

from sqlalchemy.orm import Session

from app.document_processing import extract_stories
from app.learning import Calibration, MIN_SAMPLES, accuracy_report
from app.models import Task, TaskAssignment
from app.planning import generate_plan
from tests.test_plan_audit import PORTAL, project, team
from tests.test_replan import DOC, make_member, make_plan


def finish_tasks(client, project_id, count, started="2026-11-03T09:00:00", completed="2026-11-04T17:00:00", planned=("2026-11-03", "2026-11-03")):
    """Mark `count` tasks completed: planned for 1 working day, actually took 2 (ratio 2.0)."""
    with Session(client.app.state.test_engine) as db:
        tasks = db.query(Task).filter(Task.project_id == project_id).order_by(Task.task_order).limit(count).all()
        for task in tasks:
            task.status, task.remaining_hours = "Completed", 0
            task.started_at, task.completed_at = started, completed
            task.start_date, task.end_date = planned
        db.commit()
        return [task.id for task in tasks]


def test_factor_needs_enough_samples_and_shrinks_towards_one():
    few = Calibration([{"member_id": "A", "phase": "Backend", "ratio": 2.0}] * (MIN_SAMPLES - 1))
    assert few("A", "Backend") == 1.0
    enough = Calibration([{"member_id": "A", "phase": "Backend", "ratio": 2.0}] * 3)
    assert enough("A", "Backend") == 1.5            # 1 + (2.0 - 1) * 3 / (3 + 3)
    many = Calibration([{"member_id": "A", "phase": "Backend", "ratio": 2.0}] * 30)
    assert 1.85 < many("A", "Backend") < 1.95       # more evidence, less shrinking
    assert enough("someone else", "Backend") == 1.5  # falls back to the team-wide phase evidence
    assert enough("A", "Frontend") == 1.5            # and to the person's overall record
    assert enough("B", "Frontend") == 1.0            # no evidence anywhere


def test_small_gaps_are_ignored_and_fast_people_get_trimmed_estimates():
    accurate = Calibration([{"member_id": "A", "phase": "QA", "ratio": 1.02}] * 5)
    assert accurate("A", "QA") == 1.0
    fast = Calibration([{"member_id": "A", "phase": "QA", "ratio": 0.5}] * 6)
    assert fast("A", "QA") < 0.8


def test_accuracy_report_labels_slow_and_learning_people(client):
    slow = make_member(client, name="Slow Sam")
    # Nia is on the team but unavailable for the whole project, so she never gets work and has nothing to learn from
    make_member(client, name="New Nia", available_from="2019-01-01", available_until="2019-01-02")
    project_id, _plan = make_plan(client, [slow])
    finish_tasks(client, project_id, 2)

    early = client.get("/api/estimate-accuracy", params={"today": "2026-11-20"}).json()
    sam = next(m for m in early["members"] if m["name"] == "Slow Sam")
    assert sam["samples"] == 2 and sam["learned"] is False and sam["applied_factor"] is None
    assert "Learning: 2 of 3" in sam["label"]

    finish_tasks(client, project_id, 4)
    report = client.get("/api/estimate-accuracy", params={"today": "2026-11-20"}).json()
    sam = next(m for m in report["members"] if m["name"] == "Slow Sam")
    nia = next(m for m in report["members"] if m["name"] == "New Nia")
    assert sam["learned"] is True and sam["avg_ratio"] == 2.0
    assert 1.5 <= sam["applied_factor"] <= 1.6
    assert "longer than planned" in sam["label"]
    assert nia["samples"] == 0 and nia["avg_ratio"] is None
    assert report["samples"] == 4


def test_outliers_are_clamped_and_old_history_is_ignored(client):
    member = make_member(client, name="Odd Olu")
    project_id, _plan = make_plan(client, [member])
    finish_tasks(client, project_id, 3, started="2026-11-02T09:00:00", completed="2026-12-30T09:00:00")  # ~40 working days vs 1 planned
    report = accuracy_report_via_session(client, date(2027, 1, 5))
    person = report["members"][0]
    assert person["avg_ratio"] == 2.5                                  # clamped, not 40
    stale = accuracy_report_via_session(client, date(2027, 9, 1))      # over 180 days later: history expired
    assert stale["samples"] == 0 and stale["members"][0]["avg_ratio"] is None


def accuracy_report_via_session(client, today):
    with Session(client.app.state.test_engine) as db:
        return accuracy_report(db, today)


def test_new_plans_use_the_learned_factor_and_explain_it(client):
    member = make_member(client, name="Careful Cal")
    first_project, first_plan = make_plan(client, [member])
    baseline = {t["phase"]: t["effort_hours"] for t in first_plan["tasks"]}
    finish_tasks(client, first_project, 4)

    second = client.post("/api/projects", json={
        "name": "Learned", "description": "x", "project_type": "Web Application",
        "start_date": "2026-11-02", "deadline": "2026-12-18", "member_ids": [member["id"]],
    }).json()["id"]
    client.post(f"/api/projects/{second}/documents", files={"file": ("s.txt", DOC)})
    plan = client.post(f"/api/projects/{second}/generate-plan").json()

    adjusted = [t for t in plan["tasks"] if t["assignee_id"] and t["phase"] in baseline and t["effort_hours"] > baseline[t["phase"]]]
    assert adjusted, "estimates should grow for someone who runs over"
    assert all("Estimate adjusted" in t["rationale"] for t in adjusted)
    assert plan["summary"]["estimates_adjusted"] >= len(adjusted)
    for task in adjusted:
        ratio = task["effort_hours"] / baseline[task["phase"]]
        assert 1.3 <= ratio <= 1.7


def test_planner_applies_a_factor_only_to_the_person_it_describes():
    proj = project()
    plain = {t["id"]: t for t in generate_plan(proj, extract_stories(PORTAL))["tasks"]}
    slowed = generate_plan(proj, extract_stories(PORTAL), calibration=lambda member_id, phase: 1.5 if member_id == "BE1" else 1.0)
    kept_by_ben = [t for t in slowed["tasks"] if t["assignee_id"] == "BE1"]
    assert kept_by_ben, "the senior backend developer should still own work"
    for task in kept_by_ben:
        assert task["effort_hours"] > plain[task["id"]]["effort_hours"]            # stretched for Ben
        assert "Estimate adjusted x1.5" in task["rationale"]
    for task in slowed["tasks"]:
        if task["assignee_id"] != "BE1":
            assert task["effort_hours"] == plain[task["id"]]["effort_hours"]       # everyone else unchanged
            assert "Estimate adjusted" not in task["rationale"]
    assert slowed["summary"]["estimates_adjusted"] == len(kept_by_ben)
