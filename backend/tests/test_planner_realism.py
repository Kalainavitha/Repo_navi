from app.document_processing import extract_stories
from app.planning import generate_plan

BILLING = """
As a customer, I want to sign in with email and password so that I can access my account securely.
As a customer, I want to view my invoices on a dashboard so that I can track billing history.
As an admin, I want to export billing reports to CSV so that finance can reconcile payments.
"""
WAREHOUSE = """
As a warehouse operator, I want to scan barcodes on a mobile screen so that I can update inventory counts.
As a manager, I want a real-time stock level chart so that I can decide when to reorder.
As a supplier, I want an API to push shipment data so that stock is synchronised automatically.
"""
BOOKEND_TITLES = {"Set up repository, environments and CI/CD", "Release preparation and user acceptance testing"}


def team():
    return [
        {"id": "SR", "name": "Senior", "role": "Backend Developer", "skills": ["python", "fastapi", "sql"], "experience": 10, "hours_per_day": 8, "allocation": 100},
        {"id": "JR", "name": "Junior", "role": "Backend Developer", "skills": ["python"], "experience": 1, "hours_per_day": 8, "allocation": 100},
        {"id": "FE", "name": "Frontend", "role": "Frontend Developer", "skills": ["react", "typescript"], "experience": 5, "hours_per_day": 8, "allocation": 100},
        {"id": "QA", "name": "Tester", "role": "QA Engineer", "skills": ["testing"], "experience": 4, "hours_per_day": 8, "allocation": 100},
    ]


def project(**extra):
    base = {
        "name": "P", "project_type": "Web Application", "start_date": "2026-11-02", "deadline": "2026-12-31",
        "working_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], "hours_per_day": 8, "holidays": [],
        "complexity": "Medium", "priority": "Medium", "buffer_percent": 10, "members": team(),
    }
    base.update(extra)
    return base


def bookings_from(plan, bookings=None):
    result = {member: dict(days) for member, days in (bookings or {}).items()}
    for task in plan["tasks"]:
        for allocation in task["daily_allocations"]:
            days = result.setdefault(task["assignee_id"], {})
            days[allocation["date"]] = days.get(allocation["date"], 0) + allocation["hours"]
    return result


def test_second_plan_does_not_copy_first_plan_split():
    first = generate_plan(project(), extract_stories(BILLING))
    second = generate_plan(project(), extract_stories(WAREHOUSE))
    first_titles = {task["title"] for task in first["tasks"]} - BOOKEND_TITLES
    second_titles = {task["title"] for task in second["tasks"]} - BOOKEND_TITLES
    assert first_titles.isdisjoint(second_titles)
    assert [t["effort_hours"] for t in first["tasks"]] != [t["effort_hours"] for t in second["tasks"]]


def test_each_task_has_its_own_short_summary_not_the_story_text():
    stories = extract_stories(BILLING)
    plan = generate_plan(project(), stories)
    summaries = [task["summary"] for task in plan["tasks"]]
    assert all(summaries)
    assert all(len(summary) <= 150 for summary in summaries)
    assert len(set(summaries)) == len(summaries)
    story_texts = {story["description"] for story in stories}
    assert all(task["description"] not in story_texts for task in plan["tasks"])


def test_word_boundary_matching_does_not_invent_phases():
    # "build", "guide" and "capital" only contain "ui", "id" and "api" as substrings.
    stories = [{"id": "ST-001", "title": "Capital guide", "description": "We build a capital guide for newcomers.", "acceptance_criteria": [], "priority": "Medium", "dependencies": []}]
    plan = generate_plan(project(project_type="Other"), stories)
    phases = {task["phase"] for task in plan["tasks"]}
    assert "Frontend" not in phases and "Backend" not in phases


def test_high_priority_task_goes_to_most_experienced_qualified_member():
    plan = generate_plan(project(), extract_stories(BILLING))
    backend_high = [t for t in plan["tasks"] if t["phase"] == "Backend" and t["priority"] == "High"]
    assert backend_high
    assert backend_high[0]["assignee_id"] == "SR"


def test_low_priority_work_is_not_all_given_to_the_senior():
    plan = generate_plan(project(), extract_stories(BILLING))
    assignees = {t["assignee_id"] for t in plan["tasks"]}
    assert len(assignees) >= 3


def test_busy_senior_gives_way_and_nobody_is_double_booked_across_projects():
    first = generate_plan(project(), extract_stories(BILLING))
    first_bookings = bookings_from(first)
    second = generate_plan(project(), extract_stories(WAREHOUSE), first_bookings)
    combined = bookings_from(second, first_bookings)
    assert all(hours <= 8.001 for days in combined.values() for hours in days.values())
    assert second["workloads"]["SR"]["other_project_hours"] > 0
    assert any(risk["type"] == "shared" for risk in second["summary"]["risks"])


def test_risks_are_structured_and_flag_missed_deadline():
    plan = generate_plan(project(deadline="2026-11-06", members=team()[:1]), extract_stories(BILLING))
    risks = plan["summary"]["risks"]
    assert risks and all({"type", "severity", "message"} <= set(risk) for risk in risks)
    assert any(risk["type"] == "deadline" and risk["severity"] == "High" for risk in risks)
    assert plan["summary"]["risk_level"] == "High"
    assert plan["summary"]["risk_score"] > 0
    assert all(task["risk_level"] in {"Low", "Medium", "High"} for task in plan["tasks"])
    assert isinstance(plan["summary"]["warnings"], list)


def test_infeasible_task_does_not_consume_calendar_capacity():
    member = {"id": "M", "name": "Solo", "role": "Backend Developer", "skills": ["python"], "experience": 5, "hours_per_day": 8, "allocation": 100, "available_until": "2026-11-03"}
    plan = generate_plan(project(members=[member], deadline="2026-11-03"), extract_stories(BILLING))
    assert plan["summary"]["unassigned_tasks"] >= 1
    scheduled = sum(a["hours"] for t in plan["tasks"] for a in t["daily_allocations"])
    assert scheduled <= 16.001


def test_pasted_document_headings_become_clean_task_names():
    messy = (
        "User Story: Dashboard Landing Page Simple dashboard landing page Â· Draft for review "
        "Story ID DASH-001 (draft) Priority Medium Feature Dashboard / Landing Page Status Draft"
    )
    stories = [{"id": "ST-001", "title": messy, "description": messy, "acceptance_criteria": [], "priority": "Medium", "dependencies": []}]
    plan = generate_plan(project(), stories)
    assert plan["tasks"]
    for task in plan["tasks"]:
        text = f'{task["title"]} {task["summary"]}'
        assert "Story ID" not in text and "Priority" not in text and "Draft" not in text and "User Story" not in text
        assert len(task["summary"]) <= 150
    assert any("Dashboard Landing Page" in task["title"] for task in plan["tasks"])


def test_feature_names_read_naturally_in_summaries():
    stories = extract_stories("As a logged-in user, I want to see a simple dashboard landing page after signing in, so that I can find my way around.")
    plan = generate_plan(project(), stories)
    summaries = " ".join(task["summary"] for task in plan["tasks"])
    assert "for see a" not in summaries.lower()
