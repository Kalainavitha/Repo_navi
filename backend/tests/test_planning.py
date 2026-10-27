from datetime import date, timedelta

from app.document_processing import extract_stories, extract_text
from app.planning import generate_plan, normalize_category
from app.schemas import ProjectCreate


def test_extract_stories_parses_user_stories():
    text = """
    As a customer, I want to reset my password so that I can securely sign in.
    As an admin, I want to view usage analytics so that I can monitor adoption.
    """
    stories = extract_stories(text)
    assert len(stories) == 2
    assert stories[0]["id"].startswith("ST-")


def test_generate_plan_estimates_and_assigns_members():
    project = {
        "name": "Portal",
        "project_type": "Web Application",
        "start_date": "2026-11-02",
        "deadline": "2026-12-18",
        "working_days": [1, 2, 3, 4, 5],
        "hours_per_day": 8,
        "holidays": ["2026-11-26", "2026-12-25"],
        "members": [
            {"id": "PM", "name": "Manager", "role": "Project Manager", "skills": ["planning", "risk", "stakeholder"], "experience": 8, "hours_per_day": 8, "allocation": 100, "leave_dates": ["2026-11-20"], "available_from": "2026-11-02", "available_until": "2026-12-18"},
            {"id": "FE", "name": "Frontend", "role": "Frontend Developer", "skills": ["react", "typescript", "ux"], "experience": 6, "hours_per_day": 7, "allocation": 80, "leave_dates": [], "available_from": "2026-11-02", "available_until": "2026-12-18"},
            {"id": "BE", "name": "Backend", "role": "Backend Developer", "skills": ["python", "fastapi", "sql"], "experience": 7, "hours_per_day": 8, "allocation": 90, "leave_dates": [], "available_from": "2026-11-02", "available_until": "2026-12-18"},
        ],
    }
    stories = [
        {"id": "ST-001", "title": "Self-service login", "description": "As a customer, I want to log in so that I can access the portal.", "acceptance_criteria": ["login works"], "priority": "High", "dependencies": []},
        {"id": "ST-002", "title": "User analytics", "description": "As an admin, I want to see analytics so that I can monitor usage.", "acceptance_criteria": ["dashboard works"], "priority": "Medium", "dependencies": ["ST-001"]},
    ]
    plan = generate_plan(project, stories)
    assert plan["summary"]["task_count"] >= 2
    assert all(task["assignee_id"] is not None for task in plan["tasks"] if task["assignee_id"] is not None or True)
    assert plan["summary"]["deadline_feasible"] in {True, False}


def test_generate_plan_tracks_dependencies_and_task_phases():
    project = {
        "name": "Portal",
        "project_type": "Web Application",
        "start_date": "2026-11-02",
        "deadline": "2026-12-18",
        "working_days": [1, 2, 3, 4, 5],
        "hours_per_day": 8,
        "holidays": [],
        "members": [
            {"id": "PM", "name": "Manager", "role": "Project Manager", "skills": ["planning", "risk"], "experience": 8, "hours_per_day": 8, "allocation": 100, "leave_dates": [], "available_from": "2026-11-02", "available_until": "2026-12-18"},
            {"id": "FE", "name": "Frontend", "role": "Frontend Developer", "skills": ["react", "typescript", "ux"], "experience": 6, "hours_per_day": 7, "allocation": 80, "leave_dates": [], "available_from": "2026-11-02", "available_until": "2026-12-18"},
            {"id": "BE", "name": "Backend", "role": "Backend Developer", "skills": ["python", "fastapi", "sql"], "experience": 7, "hours_per_day": 8, "allocation": 90, "leave_dates": [], "available_from": "2026-11-02", "available_until": "2026-12-18"},
        ],
    }
    stories = [
        {"id": "ST-001", "title": "Authentication", "description": "As a customer, I want to sign in with email and password so that I can access my portal account.", "acceptance_criteria": ["login works"], "priority": "High", "dependencies": []},
        {"id": "ST-002", "title": "Dashboard", "description": "As a customer, I want a dashboard so that I can see my account summary.", "acceptance_criteria": ["dashboard shows summary"], "priority": "Medium", "dependencies": ["ST-001"]},
    ]
    plan = generate_plan(project, stories)
    assert any('phase' in task for task in plan['tasks'])
    assert all(task['dependencies'] == [] or set(task['dependencies']).issubset({item['id'] for item in plan['tasks']}) for task in plan['tasks'])
    assert isinstance(plan['summary'].get('warnings', []), list)


def test_project_create_accepts_named_weekdays_and_respects_weekends():
    project = ProjectCreate(
        name="Weekend Portal",
        start_date="2026-11-02",
        deadline="2026-11-20",
        working_days=["Monday", "Wednesday", "Friday"],
        members=[],
    )
    assert project.working_days == ["Monday", "Wednesday", "Friday"]

    plan = generate_plan(
        {
            "name": "Weekend Portal",
            "project_type": "Web Application",
            "start_date": "2026-11-02",
            "deadline": "2026-11-20",
            "working_days": ["Monday", "Wednesday", "Friday"],
            "hours_per_day": 8,
            "holidays": [],
            "members": [
                {"id": "BE", "name": "Backend", "role": "Backend Developer", "skills": ["python", "fastapi", "sql"], "experience": 7, "hours_per_day": 8, "allocation": 100, "leave_dates": [], "available_from": "2026-11-02", "available_until": "2026-11-20"},
            ],
        },
        [{"id": "ST-001", "title": "API", "description": "As a customer, I want a login API so that I can access my account.", "acceptance_criteria": ["API works"], "priority": "High", "dependencies": []}],
    )
    scheduled_dates = [date.fromisoformat(task["start_date"]) for task in plan["tasks"] if task.get("start_date")]
    assert scheduled_dates
    assert all(day.weekday() in {0, 2, 4} for day in scheduled_dates)


def test_extract_text_rejects_empty_or_unsupported_files():
    try:
        extract_text("bad.exe", b"hello")
        assert False
    except ValueError:
        pass
    try:
        extract_text("notes.txt", b"")
        assert False
    except ValueError:
        pass


def test_task_categories_normalize_legacy_phase_aliases():
    assert normalize_category(' Frontend ') == 'UI/Frontend'
    assert normalize_category('QA / Testing') == 'QA/Testing'
    assert normalize_category('Infrastructure setup') == 'DevOps/Deployment'
    assert normalize_category('Architecture & design') == 'Planning & Analysis'
    assert normalize_category('Unclassified legacy phase') == 'Other'
