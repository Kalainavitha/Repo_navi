from datetime import date, timedelta
import re

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAY_LOOKUP = {name.lower(): index for index, name in enumerate(WEEKDAY_NAMES)}
TASK_CATEGORIES = ["UI/Frontend", "Backend", "QA/Testing", "Integration", "DevOps/Deployment", "Documentation", "Planning & Analysis", "Other"]


def normalize_category(value):
    key = re.sub(r"[^a-z0-9]", "", str(value or "").lower())
    aliases = {
        "frontend": "UI/Frontend",
        "frontendbuild": "UI/Frontend",
        "ui": "UI/Frontend",
        "uifrontend": "UI/Frontend",
        "backend": "Backend",
        "api": "Backend",
        "backendapi": "Backend",
        "backendapis": "Backend",
        "datamodel": "Backend",
        "qatesting": "QA/Testing",
        "qa": "QA/Testing",
        "testing": "QA/Testing",
        "qualityassurance": "QA/Testing",
        "integration": "Integration",
        "devops": "DevOps/Deployment",
        "deployment": "DevOps/Deployment",
        "devopsdeployment": "DevOps/Deployment",
        "infrastructuresetup": "DevOps/Deployment",
        "releasepreparation": "DevOps/Deployment",
        "documentation": "Documentation",
        "requirementsanalysis": "Planning & Analysis",
        "architecturedesign": "Planning & Analysis",
        "planninganalysis": "Planning & Analysis",
        "other": "Other",
    }
    return aliases.get(key, "Other")


def _normalize_workdays(value):
    raw = value or ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    if isinstance(raw, str):
        raw = [part.strip() for part in raw.split(",") if part.strip()]
    mapped = set()
    for item in raw:
        if isinstance(item, int):
            index = item
        elif isinstance(item, str):
            key = item.strip().lower()
            if key.isdigit():
                index = int(key)
            else:
                index = WEEKDAY_LOOKUP.get(key)
                if index is None:
                    index = WEEKDAY_LOOKUP.get(key.replace("day", "").strip())
        else:
            continue
        if 0 <= index <= 6:
            mapped.add(index)
    if not mapped:
        mapped = set(range(5))
    return mapped


def _skills(member):
    return {skill.strip().lower() for skill in member.get("skills", []) if skill.strip()}


def _normalize_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _task_phases(description: str, project_type: str):
    text = description.lower()
    if any(keyword in text for keyword in ["login", "signin", "sign in", "password", "reset", "authentication", "otp", "token", "session"]):
        return [
            ("Frontend", "Frontend Developer", ["react", "ui", "ux", "login", "password", "reset"], "Build sign-in and password reset UI", 5.0),
            ("Frontend", "Frontend Developer", ["react", "ui", "ux", "responsive", "error"], "Add validation, accessibility, and error states", 4.0),
            ("Backend", "Backend Developer", ["api", "auth", "security", "token", "login"], "Implement authentication and token validation API", 7.0),
            ("Backend", "Backend Developer", ["password", "reset", "email", "security", "database"], "Implement password reset flow and verification logic", 6.0),
            ("Integration", "Full-Stack Developer", ["integration", "frontend", "backend", "api", "workflow"], "Connect UI flows to the authentication and reset endpoints", 5.0),
            ("QA / Testing", "QA Engineer", ["qa", "test", "validation", "acceptance", "verify"], "Verify login, reset, and edge-case scenarios", 4.0),
            ("Documentation", "Project Manager", ["documentation", "guide", "readme", "support"], "Document the login and reset workflow for support and rollout", 2.0),
        ]

    phases = [
        ("Requirements analysis", "Business Analyst", ["analysis", "requirements", "needs", "workflow", "business"], "Confirm scope and acceptance criteria", 3.0),
        ("Architecture & design", "Project Manager", ["architecture", "design", "system", "integration", "workflow"], "Define the architecture and implementation approach", 4.0),
        ("Infrastructure setup", "DevOps Engineer", ["deploy", "cloud", "environment", "infrastructure", "setup"], "Prepare environments and deployment prerequisites", 3.0),
        ("Data model", "Backend Developer", ["database", "schema", "model", "sql", "data"], "Create the supporting data model and persistence layers", 4.0),
        ("Backend", "Backend Developer", ["api", "backend", "service", "auth", "security", "database"], "Build the service layer and backend APIs", 5.0),
        ("Frontend", "Frontend Developer", ["frontend", "ui", "ux", "dashboard", "page", "screen", "web", "mobile"], "Build the user-facing workflow and screens", 5.0),
        ("Integration", "Full-Stack Developer", ["integrat", "frontend", "backend", "api", "workflow"], "Connect the frontend flow to backend services", 5.0),
        ("QA / Testing", "QA Engineer", ["qa", "test", "validation", "acceptance", "verify"], "Execute validation and fix defects", 4.0),
        ("DevOps / Deployment", "DevOps Engineer", ["release", "deploy", "configuration", "monitoring"], "Prepare release checklist and deployment checkpoints", 2.0),
    ]

    matched = []
    for phase, role, skills, task_title, effort in phases:
        if any(keyword in text for keyword in skills) or (project_type == "Web Application" and phase in {"Frontend", "Backend", "Integration"}):
            matched.append((phase, role, skills, task_title, effort))

    if not matched:
        matched = [("Implementation", "Full-Stack Developer", ["feature", "build", "deliver"], "Build the core feature set", 4.0)]

    return matched


def _candidate_members(members, required_skills, preferred_role):
    candidates = []
    for member in members:
        skills = _skills(member)
        overlap = sum(1 for skill in required_skills if skill in skills)
        role_match = preferred_role.lower() in member.get("role", "").lower()
        score = overlap * 4 + (2 if role_match else 0) + min(member.get("experience", 0), 10) * 0.1
        if score > 0:
            candidates.append((score, member))
    candidates.sort(key=lambda item: (-item[0], item[1].get("name", "")))
    return candidates


def _schedule_task(task, task_index, tasks, members, project, workloads, member_calendar, story_lookup):
    task["daily_allocations"] = []
    member_id = task.get("assignee_id")
    if not member_id:
        return task

    member = next((member for member in members if member["id"] == member_id), None)
    if not member:
        task["assignee_id"] = None
        task["assignee_name"] = None
        task["warning"] = "The task has no valid assignee on the current project roster."
        return task

    start_date = _normalize_date(project.get("start_date"))
    deadline = _normalize_date(project.get("deadline"))
    project_workdays = _normalize_workdays(project.get("working_days", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]))
    member_workdays = _normalize_workdays(member.get("working_days", project.get("working_days", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])))
    workdays = project_workdays & member_workdays
    holiday_dates = {_normalize_date(value) for value in project.get("holidays", []) if _normalize_date(value)}
    leave_dates = {_normalize_date(value) for value in member.get("leave_dates", []) if _normalize_date(value)}
    available_from = _normalize_date(member.get("available_from"))
    available_until = _normalize_date(member.get("available_until"))
    daily_capacity = float(member.get("hours_per_day", project.get("hours_per_day", 8))) * float(member.get("allocation", 100)) / 100
    requested_start = _normalize_date(task.get("requested_start_date"))
    current_date = max(start_date, requested_start) if requested_start else start_date
    for dep_id in task.get("dependencies", []):
        dependency = next((candidate for candidate in tasks if candidate["id"] == dep_id), None)
        if dependency and dependency.get("end_date"):
            dep_end = _normalize_date(dependency["end_date"])
            if dep_end:
                current_date = max(current_date, dep_end + timedelta(days=1))

    cursor = current_date
    selected_dates = []
    remaining = float(task["effort_hours"])
    max_window = deadline + timedelta(days=180) if deadline else start_date + timedelta(days=365)
    while remaining > 0 and cursor <= max_window:
        day_value = cursor.isoformat()
        day_check = cursor.weekday() in workdays and cursor not in holiday_dates and cursor not in leave_dates
        availability_ok = True
        if available_from and cursor < available_from:
            availability_ok = False
        if available_until and cursor > available_until:
            availability_ok = False
        if day_check and availability_ok:
            allocated = member_calendar.get(member["id"], {}).get(day_value, 0.0)
            capacity_left = max(0.0, daily_capacity - allocated)
            if capacity_left > 0:
                consumed = min(remaining, capacity_left)
                remaining -= consumed
                member_calendar.setdefault(member["id"], {})[day_value] = allocated + consumed
                selected_dates.append(cursor)
                task["daily_allocations"].append({"date": day_value, "hours": round(consumed, 2)})
        cursor += timedelta(days=1)

    if remaining > 0 or not selected_dates:
        task["assignee_id"] = None
        task["assignee_name"] = None
        task["daily_allocations"] = []
        task["warning"] = f"No feasible schedule was possible for {task['title']} within the current team capacity."
        return task

    task["start_date"] = selected_dates[0].isoformat()
    task["end_date"] = selected_dates[-1].isoformat()
    workloads[member["id"]]["assigned_hours"] += float(task["effort_hours"])
    return task


def reschedule_tasks(project: dict, members: list[dict], tasks: list[dict]):
    workloads = {member["id"]: {"assigned_hours": 0.0, "available_hours": 0.0, "utilization": 0.0} for member in members}
    member_calendar = {member["id"]: {} for member in members}
    scheduled = []
    for index, task in enumerate(tasks):
        assigned_before = task.get("assignee_id")
        result = _schedule_task(task, index, scheduled, members, project, workloads, member_calendar, {})
        if assigned_before and not result.get("assignee_id"):
            raise ValueError(result.get("warning") or f"No feasible schedule was possible for {task['title']}.")
        scheduled.append(result)
    return scheduled


def generate_plan(project: dict, stories: list[dict]):
    members = project.get("members", [])
    project_start = _normalize_date(project.get("start_date")) or date.today()
    project_deadline = _normalize_date(project.get("deadline"))
    workdays = _normalize_workdays(project.get("working_days", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]))
    holidays = {_normalize_date(value) for value in project.get("holidays", []) if _normalize_date(value)}
    workloads = {member["id"]: {"assigned_hours": 0.0, "available_hours": 0.0, "utilization": 0.0} for member in members}
    member_calendar = {member["id"]: {} for member in members}
    story_lookup = {story["id"]: story for story in stories}
    tasks = []
    warnings = []

    for story in stories:
        story_id = story.get("id", f"ST-{len(tasks) + 1:03d}")
        story_tasks = _task_phases(story.get("description", ""), project.get("project_type", ""))
        previous_story_task_id = None
        for index, (phase, role, required_skills, task_title, effort_base) in enumerate(story_tasks):
            task_id = f"TSK-{len(tasks) + 1:03d}"
            dependencies = []
            if story.get("dependencies"):
                for dependency_id in story.get("dependencies", []):
                    dependency_story = story_lookup.get(dependency_id)
                    if dependency_story:
                        candidate = next((task for task in tasks if task.get("story_ids") == [dependency_id]), None)
                        if candidate:
                            dependencies.append(candidate["id"])
            if previous_story_task_id and not dependencies:
                dependencies = [previous_story_task_id]

            candidates = _candidate_members(members, required_skills, role)
            assignee = candidates[0][1] if candidates else None
            task = {
                "id": task_id,
                "title": f"{task_title}: {story.get('title', 'Requirement')}",
                "description": story.get("description", "") + (f" Acceptance criteria: {'; '.join(story.get('acceptance_criteria', []))}" if story.get("acceptance_criteria") else ""),
                "story_ids": [story_id],
                "category": normalize_category(phase),
                "phase": phase,
                "effort_hours": max(2.0, round(float(effort_base) * (1.2 if story.get("priority") == "High" else 1.0), 1)),
                "remaining_hours": max(2.0, round(float(effort_base) * (1.2 if story.get("priority") == "High" else 1.0), 1)),
                "priority": story.get("priority", "Medium"),
                "required_skills": required_skills,
                "assignee_id": assignee["id"] if assignee else None,
                "assignee_name": assignee["name"] if assignee else None,
                "dependencies": dependencies,
                "acceptance_criteria": story.get("acceptance_criteria", []) or [f"Confirm {story.get('title', 'the requirement')} is working as expected."],
                "start_date": None,
                "end_date": None,
                "status": "Pending",
                "uncertain": False,
                "rationale": f"Planned in the {phase.lower()} phase to satisfy the requirement and respect the dependency chain.",
                "warning": None,
                "source_story": story.get("title", "Requirement"),
            }

            if not assignee:
                task["warning"] = f"No team member matched the required skills for {phase}."
                warnings.append(task["warning"])
            else:
                task["assignee_id"] = assignee["id"]
                task["assignee_name"] = assignee["name"]
            task = _schedule_task(task, index, tasks, members, project, workloads, member_calendar, story_lookup)
            if task.get("warning"):
                warnings.append(task["warning"])
            tasks.append(task)
            previous_story_task_id = task["id"]

    for story in stories:
        for dependency_id in story.get("dependencies", []):
            if dependency_id not in story_lookup:
                warnings.append(f"Story {story.get('id')} references a missing dependency: {dependency_id}.")

    for task in tasks:
        if task.get("dependencies") and not task["dependencies"]:
            continue
        invalid = [dep for dep in task["dependencies"] if dep not in {item["id"] for item in tasks}]
        if invalid:
            warnings.append(f"Task {task['id']} depends on unknown tasks: {', '.join(invalid)}.")

    for member in members:
        available_hours = 0.0
        cursor = project_start
        end = project_deadline or (project_start + timedelta(days=180))
        while cursor <= end:
            member_workdays = _normalize_workdays(member.get("working_days", project.get("working_days", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])))
            if cursor.weekday() in (workdays & member_workdays) and cursor not in holidays and cursor not in {_normalize_date(v) for v in member.get("leave_dates", []) if _normalize_date(v)}:
                available_from = _normalize_date(member.get("available_from"))
                available_until = _normalize_date(member.get("available_until"))
                if (not available_from or cursor >= available_from) and (not available_until or cursor <= available_until):
                    available_hours += float(member.get("hours_per_day", project.get("hours_per_day", 8))) * float(member.get("allocation", 100)) / 100
            cursor += timedelta(days=1)
        workloads[member["id"]]["available_hours"] = round(available_hours, 1)
        assigned = workloads[member["id"]]["assigned_hours"]
        workloads[member["id"]]["utilization"] = round((assigned / available_hours) * 100, 1) if available_hours else 0.0

    scheduled_end_dates = [_normalize_date(task["end_date"]) for task in tasks if task.get("end_date")]
    projected_completion = max(scheduled_end_dates).isoformat() if scheduled_end_dates else None
    unassigned = sum(1 for task in tasks if not task.get("assignee_id"))
    deadline_feasible = True
    if project_deadline and projected_completion:
        deadline_feasible = date.fromisoformat(projected_completion) <= project_deadline
    if not deadline_feasible:
        warnings.append("The generated schedule exceeds the target deadline.")

    summary = {
        "story_count": len(stories),
        "task_count": len(tasks),
        "completed_tasks": 0,
        "in_progress_tasks": 0,
        "pending_tasks": sum(1 for task in tasks if task["status"] == "Pending"),
        "blocked_tasks": 0,
        "unassigned_tasks": unassigned,
        "estimated_hours": round(sum(task["effort_hours"] for task in tasks), 1),
        "remaining_hours": round(sum(task["remaining_hours"] for task in tasks), 1),
        "progress_percent": 0,
        "projected_completion": projected_completion,
        "deadline_feasible": deadline_feasible,
        "risks": list(dict.fromkeys(warnings)),
        "warnings": list(dict.fromkeys(warnings)),
    }
    return {"stories": stories, "tasks": tasks, "workloads": workloads, "summary": summary}
