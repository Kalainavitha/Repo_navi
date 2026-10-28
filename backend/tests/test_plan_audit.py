"""Real-world audit of generated plans: capacity, calendars, dependencies, priority and experience."""
from collections import defaultdict
from datetime import date

import pytest

from app.document_processing import extract_stories
from app.planning import generate_plan

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
TECHNICAL = {"Backend", "Frontend", "Integration", "QA / Testing", "Infrastructure setup", "Implementation"}


def person(id_, name, role, skills, experience, hours=8, **extra):
    return {"id": id_, "name": name, "role": role, "skills": skills, "experience": experience, "hours_per_day": hours,
            "allocation": 100, "working_days": WEEKDAYS, "leave_dates": [], **extra}


def team():
    return [
        person("PM", "Priya", "Team Lead", ["planning", "stakeholder"], 12, is_lead=True),
        person("BE1", "Ben", "Backend Developer", ["python", "fastapi", "sql", "security"], 9),
        person("BE2", "Bea", "Backend Developer", ["python", "sql"], 4),
        person("BE3", "Joe", "Backend Developer", ["python"], 1),
        person("FE1", "Fay", "Frontend Developer", ["react", "typescript", "ux"], 8),
        person("FE2", "Finn", "Frontend Developer", ["react"], 1),
        person("QA", "Quinn", "QA Engineer", ["testing", "automation"], 5),
        person("DO", "Dev", "DevOps Engineer", ["aws", "docker", "ci"], 6),
    ]


PORTAL = """
As a customer, I want to sign in with email and password so that I can access my account securely.
As a customer, I want to pay invoices online with my card so that I can settle my balance. Payments must be secure and compliant.
As a customer, I want to view my invoice history on a dashboard so that I can track billing.
As an admin, I want to export billing reports to CSV so that finance can reconcile payments.
As a customer, I want to receive email notifications when an invoice is due so that I never miss a payment.
As an admin, I want to deploy the portal to the cloud with monitoring so that we have uptime.
"""
WAREHOUSE = """
As an operator, I want to scan barcodes on a mobile screen so that I can update inventory counts quickly.
As a manager, I want a real-time stock level chart so that I can decide when to reorder.
As a supplier, I want an API to push shipment data so that stock is synchronised automatically.
As a manager, I want to search products by name so that I can find items fast.
"""


def project(name="P", start="2026-11-02", deadline="2026-12-18", members=None, **extra):
    return {"name": name, "project_type": "Web Application", "start_date": start, "deadline": deadline,
            "working_days": WEEKDAYS, "hours_per_day": 8, "holidays": [], "complexity": "Medium", "priority": "Medium",
            "buffer_percent": 10, "members": members if members is not None else team(), **extra}


def violations(proj, plan, before=None):
    """Hard-rule violations: capacity, calendars, hours, dependencies."""
    found = []
    members = {m["id"]: m for m in proj["members"]}
    tasks = {t["id"]: t for t in plan["tasks"]}
    load = defaultdict(float)
    for member_id, days in (before or {}).items():
        for day, hours in days.items():
            load[(member_id, day)] += hours
    for t in plan["tasks"]:
        if t["assignee_id"]:
            got = sum(a["hours"] for a in t["daily_allocations"])
            if abs(got - t["effort_hours"]) > 0.05:
                found.append(f"{t['id']} has {got}h scheduled of {t['effort_hours']}h")
        for a in t["daily_allocations"]:
            member = members[t["assignee_id"]]
            load[(member["id"], a["date"])] += a["hours"]
            day = date.fromisoformat(a["date"])
            if day.weekday() >= 5 or a["date"] in proj["holidays"]:
                found.append(f"{t['id']} on non-working day {a['date']}")
            if a["date"] in member["leave_dates"]:
                found.append(f"{t['id']} on leave {a['date']}")
            if member.get("available_from") and a["date"] < member["available_from"]:
                found.append(f"{t['id']} before availability")
            if member.get("available_until") and a["date"] > member["available_until"]:
                found.append(f"{t['id']} after availability")
            if a["date"] < proj["start_date"]:
                found.append(f"{t['id']} before project start")
        for dep in t["dependencies"]:
            end = tasks[dep].get("end_date")
            if end and t.get("start_date") and t["start_date"] <= end:
                found.append(f"{t['id']} starts before {dep} ends")
    for (member_id, day), hours in load.items():
        capacity = members[member_id]["hours_per_day"] * members[member_id]["allocation"] / 100
        if hours > capacity + 0.01:
            found.append(f"{members[member_id]['name']} overbooked {hours}h on {day}")
    return found


def bookings_of(plan, bookings=None):
    result = {k: dict(v) for k, v in (bookings or {}).items()}
    for t in plan["tasks"]:
        for a in t["daily_allocations"]:
            result.setdefault(t["assignee_id"], {})
            result[t["assignee_id"]][a["date"]] = result[t["assignee_id"]].get(a["date"], 0) + a["hours"]
    return result


def weighted_experience(plan, members, priority):
    by_id = {m["id"]: m for m in members}
    tasks = [t for t in plan["tasks"] if t["priority"] == priority and t["assignee_id"]]
    hours = sum(t["effort_hours"] for t in tasks)
    return sum(by_id[t["assignee_id"]]["experience"] * t["effort_hours"] for t in tasks) / hours if hours else 0


def test_full_team_plan_obeys_every_hard_rule_and_puts_experience_on_priority_work():
    proj = project(holidays=["2026-11-26"])
    plan = generate_plan(proj, extract_stories(PORTAL))
    assert violations(proj, plan) == []
    assert plan["summary"]["unassigned_tasks"] == 0
    assert weighted_experience(plan, proj["members"], "High") > weighted_experience(plan, proj["members"], "Low")
    # critical backend work is owned by the most experienced backend developer, not the junior
    backend_high = [t for t in plan["tasks"] if t["phase"] == "Backend" and t["priority"] == "High"]
    assert backend_high and all(t["assignee_id"] == "BE1" for t in backend_high)
    # QA work goes to QA, deployment work to DevOps
    assert {t["assignee_id"] for t in plan["tasks"] if t["phase"] == "QA / Testing" and "Deploy" not in t["title"]} <= {"QA"}
    assert {t["assignee_id"] for t in plan["tasks"] if t["title"].startswith("Prepare deployment")} == {"DO"}


def test_leave_part_time_late_joiners_and_early_leavers_are_respected():
    members = team()
    members[1] = {**members[1], "leave_dates": ["2026-11-09", "2026-11-10", "2026-11-11"]}
    members[4] = {**members[4], "hours_per_day": 4}
    members[3] = {**members[3], "available_from": "2026-11-16"}
    members[7] = {**members[7], "available_until": "2026-11-20"}
    proj = project(members=members, holidays=["2026-11-26"])
    plan = generate_plan(proj, extract_stories(PORTAL))
    assert violations(proj, plan) == []
    assert plan["summary"]["unassigned_tasks"] == 0


def test_overlapping_projects_never_double_book_and_keep_experience_on_priority_work():
    bookings = {}
    for name, doc, start, deadline, priority in (
        ("Portal", PORTAL, "2026-11-02", "2026-12-18", "High"),
        ("Warehouse", WAREHOUSE, "2026-11-09", "2026-12-18", "Medium"),
        ("Website", "As a visitor, I want to see a contact page with a form so that I can reach the company.", "2026-11-16", "2026-12-04", "Low"),
    ):
        proj = project(name, start, deadline, priority=priority)
        plan = generate_plan(proj, extract_stories(doc), bookings)
        assert violations(proj, plan, bookings) == [], name
        assert plan["summary"]["unassigned_tasks"] == 0, name
        has = {t["priority"] for t in plan["tasks"] if t["assignee_id"]}
        if {"High", "Low"} <= has:
            high = weighted_experience(plan, proj["members"], "High")
            low = weighted_experience(plan, proj["members"], "Low")
            assert high >= low, name
        bookings = bookings_of(plan, bookings)
    assert all(hours <= 8.01 for days in bookings.values() for hours in days.values())


def test_tight_deadline_switches_to_deadline_first_and_says_so():
    proj = project(deadline="2026-11-13")
    plan = generate_plan(proj, extract_stories(PORTAL))
    assert violations(proj, plan) == []
    assert plan["summary"]["deadline_feasible"] is True
    assert plan["summary"]["schedule_mode"] == "deadline_first"
    assert any(risk["type"] == "deadline_first" for risk in plan["summary"]["risks"])


def test_comfortable_deadline_keeps_experience_first():
    plan = generate_plan(project(), extract_stories(PORTAL))
    assert plan["summary"]["schedule_mode"] == "experience_first"
    assert plan["summary"]["deadline_feasible"] is True


def test_impossible_deadline_is_reported_not_hidden():
    proj = project(deadline="2026-11-04")
    plan = generate_plan(proj, extract_stories(PORTAL))
    assert violations(proj, plan) == []
    assert plan["summary"]["deadline_feasible"] is False
    assert any(risk["type"] == "deadline" and risk["severity"] == "High" for risk in plan["summary"]["risks"])


def test_high_priority_work_stays_off_juniors_when_seniors_can_meet_the_deadline():
    members = [m for m in team() if m["id"] in {"PM", "BE1", "BE3"}]
    proj = project(members=members)
    plan = generate_plan(proj, extract_stories(PORTAL))
    high_on_junior = [t for t in plan["tasks"] if t["priority"] == "High" and t["assignee_id"] == "BE3"]
    assert high_on_junior == []
    assert violations(proj, plan) == []


def test_managers_do_not_build_or_test_when_a_developer_can():
    members = [m for m in team() if m["id"] in {"PM", "BE1", "BE3"}]  # no QA, no frontend skills
    proj = project(members=members)
    plan = generate_plan(proj, extract_stories(PORTAL))
    on_manager = [t for t in plan["tasks"] if t["assignee_id"] == "PM" and t["phase"] in TECHNICAL]
    assert on_manager == []
    # the skill gap is reported instead of hidden
    assert any(risk["type"] == "skills" for risk in plan["summary"]["risks"])


def test_big_backlog_uses_the_whole_team_without_breaking_rules():
    topics = ["user profile page", "search products by name with filters", "export orders to CSV", "send email receipts",
              "admin dashboard chart of weekly sales", "reset password by email", "upload and download documents",
              "role based permissions for staff", "audit log of changes", "invoice PDF generation", "inventory report",
              "bulk import from spreadsheet", "payment refund workflow", "mobile friendly checkout page", "discount codes"]
    doc = "\n".join(f"As a user, I want {t} so that I can get my work done." for t in topics)
    proj = project(deadline="2026-12-04")
    plan = generate_plan(proj, extract_stories(doc))
    assert violations(proj, plan) == []
    assert plan["summary"]["unassigned_tasks"] == 0
    used = {t["assignee_id"] for t in plan["tasks"]}
    assert len(used) >= 6
    assert weighted_experience(plan, proj["members"], "High") >= weighted_experience(plan, proj["members"], "Low")


@pytest.mark.parametrize("seed_hours", [4, 6, 8])
def test_shorter_working_days_never_exceed_capacity(seed_hours):
    members = [{**m, "hours_per_day": seed_hours} for m in team()]
    proj = project(members=members)
    plan = generate_plan(proj, extract_stories(PORTAL))
    assert violations(proj, plan) == []
