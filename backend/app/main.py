import csv
import io
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine, get_db
from .document_processing import extract_stories, extract_text
from .models import Project, ProjectMember, Task, TaskAssignment, TaskDailyAllocation, TaskDependency, TeamMember
from .forecast import DEFAULT_RUNS, attach_to_summary, forecast_plan
from .learning import accuracy_report, build_calibration
from .report import build_report
from .report_export import EXPORT_FORMATS, export_report
from .planning import _clean_heading, generate_plan, normalize_category, rebalance_unstarted, replan_from, reschedule_tasks
from .schemas import MemberCreate, MemberUpdate, ProjectCreate, ProjectUpdate, TaskUpdate

app = FastAPI(title="GenPlan API", version="0.2.0", description="Deterministic, explainable project planning service.")
default_origins = [
    "http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:5176",
    "http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://127.0.0.1:5175", "http://127.0.0.1:5176",
]
origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", ",".join(default_origins)).split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


def member_dict(member: TeamMember):
    m = cast(Any, member)
    return {column.name: getattr(m, column.name) for column in TeamMember.__table__.columns}


def has_lead_role(*roles) -> bool:
    """A member whose role (or additional role) is Team Lead may reassign and edit tasks."""
    return any("lead" in re.findall(r"[a-z]+", str(role or "").lower()) for role in roles)


def get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found.")
    return project

def get_team_member_or_404(member_id: str, db: Session) -> TeamMember:
    member = db.get(TeamMember, member_id)
    if member is None:
        raise HTTPException(404, "Team member not found.")
    return member

def project_members(project_id: int, db: Session):
    return db.query(TeamMember).join(ProjectMember, ProjectMember.member_id == TeamMember.id).filter(ProjectMember.project_id == project_id).order_by(TeamMember.name).all()


def _generate_short_summary(description: Any, title: Any, max_length: int = 150) -> str:
    if not description:
        return str(title)
    text = re.sub(r'[#*_]+', '', str(description)) 
    text = re.sub(r'\s+', ' ', text).strip()
    match = re.search(r'^.*?[.!?](?=\s|$)', text)
    first_sentence = match.group(0) if match else text
    if len(first_sentence) > max_length:
        return first_sentence[:max_length - 1].strip() + "…"
    return first_sentence

def _legacy_task_summary(t: Any) -> str:
    """Short summary for plans created before tasks had their own summary (their description is the whole story)."""
    story = _clean_heading(t.source_story or "")
    label = (t.phase or t.category or "Task").strip()
    if story:
        return _generate_short_summary(f"{label} work for \u201c{story}\u201d.", t.title)
    return _generate_short_summary(t.description, t.title)


def task_dict(task: Task, db: Session):
    t = cast(Any, task)
    assignment = db.get(TaskAssignment, t.id)
    assignee = db.get(TeamMember, cast(Any, assignment).member_id) if assignment else None
    dependencies = [row.depends_on_task_id for row in db.query(TaskDependency).filter(TaskDependency.task_id == t.id).all()]
    
    task_summary = t.summary or _legacy_task_summary(t)

    return {
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "summary": task_summary,
        "summary_source": "task" if t.summary else "derived",
        "story_ids": t.story_ids or [],
        "source_story": t.source_story,
        "category": normalize_category(t.category or t.phase),
        "phase": t.phase,
        "effort_hours": t.effort_hours,
        "remaining_hours": t.remaining_hours,
        "priority": t.priority,
        "required_skills": t.required_skills or [],
        "acceptance_criteria": t.acceptance_criteria or [],
        "assignee_id": cast(Any, assignee).id if assignee else None,
        "assignee_name": cast(Any, assignee).name if assignee else None,
        "dependencies": dependencies,
        "start_date": t.start_date,
        "end_date": t.end_date,
        "status": t.status,
        "uncertain": t.uncertain,
        "rationale": t.rationale,
        "warning": t.warning,
        "risk_level": t.risk_level or "Low",
        "risk_note": t.risk_note,
        "started_at": t.started_at,
        "completed_at": t.completed_at,
        "manually_edited": t.manually_edited,
        "daily_allocations": [
            {"date": cast(Any, allocation).work_date, "hours": cast(Any, allocation).allocated_hours}
            for allocation in db.query(TaskDailyAllocation).filter(TaskDailyAllocation.task_id == t.id).order_by(TaskDailyAllocation.work_date).all()
        ],
    }


def other_project_bookings(db: Session, exclude_project_id: int | None = None):
    """Hours each member is already booked per day on other active (non-archived, unfinished) work."""
    query = db.query(TaskDailyAllocation.work_date, TaskDailyAllocation.allocated_hours, TaskAssignment.member_id).join(
        Task, Task.id == TaskDailyAllocation.task_id,
    ).join(
        TaskAssignment, TaskAssignment.task_id == Task.id,
    ).join(
        Project, Project.id == Task.project_id,
    ).filter(Project.archived.is_(False), Task.status != "Completed")
    if exclude_project_id is not None:
        query = query.filter(Task.project_id != exclude_project_id)
    bookings: dict[str, dict[str, float]] = {}
    for work_date, hours, member_id in query.all():
        days = bookings.setdefault(member_id, {})
        days[work_date] = days.get(work_date, 0.0) + float(hours or 0)
    return bookings


def delete_project_tasks(db: Session, project_id: int):
    task_ids = db.query(Task.id).filter(Task.project_id == project_id)
    db.query(TaskDailyAllocation).filter(TaskDailyAllocation.task_id.in_(task_ids)).delete(synchronize_session=False)
    db.query(TaskDependency).filter(TaskDependency.task_id.in_(task_ids)).delete(synchronize_session=False)
    db.query(TaskDependency).filter(TaskDependency.depends_on_task_id.in_(task_ids)).delete(synchronize_session=False)
    db.query(TaskAssignment).filter(TaskAssignment.task_id.in_(task_ids)).delete(synchronize_session=False)
    db.query(Task).filter(Task.project_id == project_id).delete(synchronize_session=False)


def project_plan(project: Project, db: Session):
    p = cast(Any, project)
    if not p.plan and not db.query(Task.id).filter(Task.project_id == p.id).first():
        return None
    base = dict(p.plan or {})
    tasks = [task_dict(task, db) for task in db.query(Task).filter(Task.project_id == p.id).order_by(Task.task_order).all()]
    counts = {status: sum(task["status"] == status for task in tasks) for status in ("Pending", "In Progress", "Completed", "Blocked")}
    summary = dict(base.get("summary") or {})
    summary.update({
        "status": p.status,
        "task_count": len(tasks),
        "completed_tasks": counts["Completed"],
        "in_progress_tasks": counts["In Progress"],
        "pending_tasks": counts["Pending"],
        "blocked_tasks": counts["Blocked"],
        "unassigned_tasks": sum(not task["assignee_id"] for task in tasks),
        "estimated_hours": round(sum(task["effort_hours"] for task in tasks), 1),
        "remaining_hours": round(sum(task["remaining_hours"] for task in tasks if task["status"] != "Completed"), 1),
        "progress_percent": round(100 * counts["Completed"] / len(tasks)) if tasks else 0,
    })
    daily_workload = {}
    members = project_members(p.id, db)
    try:
        cursor = date.fromisoformat(p.start_date) if p.start_date else None
        final_date = date.fromisoformat(p.deadline) if p.deadline else cursor
    except ValueError:
        cursor = final_date = None

    def weekday_indices(values):
        result = set()
        for value in values or []:
            if isinstance(value, int) and 0 <= value <= 6:
                result.add(value)
            elif isinstance(value, str):
                for index, name in enumerate(("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")):
                    if value.strip().lower() in (name.lower(), name[:3].lower()):
                        result.add(index)
        return result

    project_days = weekday_indices(p.working_days)
    holidays = set(p.holidays or [])
    while cursor and final_date and cursor <= final_date:
        if cursor.weekday() in project_days and cursor.isoformat() not in holidays:
            for member in members:
                m = cast(Any, member)
                member_days = weekday_indices(m.working_days or p.working_days)
                leave_dates = set(m.leave_dates or [])
                if cursor.weekday() not in member_days or cursor.isoformat() in leave_dates:
                    continue
                if m.available_from and cursor.isoformat() < m.available_from:
                    continue
                if m.available_until and cursor.isoformat() > m.available_until:
                    continue
                daily_workload[(cursor.isoformat(), m.id)] = {
                    "date": cursor.isoformat(),
                    "member_id": m.id,
                    "member_name": m.name,
                    "capacity_hours": round(m.hours_per_day * m.allocation / 100, 2),
                    "allocated_hours": 0.0,
                    "remaining_hours": round(m.hours_per_day * m.allocation / 100, 2),
                    "tasks": [],
                }
        cursor += timedelta(days=1)

    allocations = db.query(TaskDailyAllocation, Task, TaskAssignment, TeamMember).join(
        Task, Task.id == TaskDailyAllocation.task_id,
    ).join(
        TaskAssignment, TaskAssignment.task_id == Task.id,
    ).join(
        TeamMember, TeamMember.id == TaskAssignment.member_id,
    ).filter(Task.project_id == p.id).order_by(TaskDailyAllocation.work_date, Task.task_order).all()
    for allocation, task, _assignment, member in allocations:
        a, t, m = cast(Any, allocation), cast(Any, task), cast(Any, member)
        key = (a.work_date, m.id)
        item = daily_workload.setdefault(key, {
            "date": a.work_date,
            "member_id": m.id,
            "member_name": m.name,
            "capacity_hours": round(m.hours_per_day * m.allocation / 100, 2),
            "allocated_hours": 0.0,
            "remaining_hours": 0.0,
            "tasks": [],
        })
        item["allocated_hours"] = round(item["allocated_hours"] + a.allocated_hours, 2)
        item["tasks"].append({
            "id": t.id,
            "title": t.title,
            "start_date": t.start_date,
            "end_date": t.end_date,
            "effort_hours": t.effort_hours,
            "allocated_hours": a.allocated_hours,
            "status": t.status,
        })
    workload_rows = sorted(daily_workload.values(), key=lambda item: (item["date"], item["member_name"]))
    for item in workload_rows:
        item["remaining_hours"] = round(max(0.0, item["capacity_hours"] - item["allocated_hours"]), 2)
    return {
        **base,
        "id": p.id,
        "project_id": p.id,
        "name": p.name,
        "project_type": p.project_type,
        "start_date": p.start_date,
        "deadline": p.deadline,
        "status": p.status,
        "archived": p.archived,
        "stories": base.get("stories", p.stories or []),
        "tasks": tasks,
        "daily_workload": workload_rows,
        "summary": summary,
    }


def project_dict(project: Project, db: Session, include_plan=True):
    p = cast(Any, project)
    result = {column.name: getattr(p, column.name) for column in Project.__table__.columns}
    result["members"] = [member_dict(member) for member in project_members(p.id, db)]
    result["has_plan"] = bool(p.plan or db.query(Task.id).filter(Task.project_id == p.id).first())
    if include_plan:
        result["plan"] = project_plan(p, db)
    else:
        result.pop("plan", None)
        result.pop("members", None)
    return result


def add_member_to_project(project: Project, member: TeamMember, db: Session):
    p, m = cast(Any, project), cast(Any, member)
    if not db.get(ProjectMember, (p.id, m.id)):
        db.add(ProjectMember(project_id=p.id, member_id=m.id))


def create_legacy_member(data: dict, db: Session):
    member_id = str(data.get("id") or uuid4())
    member = db.get(TeamMember, member_id)
    if not member:
        member = TeamMember(
            id=member_id, name=data.get("name", "Team member"), role=data.get("role", "Team Member"),
            skills=data.get("skills") or [], experience=float(data.get("experience", 0)),
            hours_per_day=float(data.get("hours_per_day", 8)),
            working_days=data.get("working_days") or ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            allocation=float(data.get("allocation", 100)), available_from=data.get("available_from"),
            available_until=data.get("available_until"), leave_dates=data.get("leave_dates") or [],
            email=data.get("email"), notes=data.get("notes"), hourly_rate=data.get("hourly_rate"),
            additional_role=data.get("additional_role"),
            is_lead=bool(data.get("is_lead")) or has_lead_role(data.get("role"), data.get("additional_role")),
        )
        db.add(member)
        db.flush()
    return member


def weekday_indices(values):
    names = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
    result = set()
    for value in values or []:
        if isinstance(value, int) and 0 <= value <= 6:
            result.add(value)
        elif isinstance(value, str):
            key = value.strip().lower()
            for index, name in enumerate(names):
                if key in {name, name[:3]}:
                    result.add(index)
    return result


def migrate_daily_allocations(db: Session):
    calendar = {}
    pending_allocations = {}
    for allocation in db.query(TaskDailyAllocation).all():
        a = cast(Any, allocation)
        key = (a.task_id, a.work_date)
        calendar[key] = a.allocated_hours
    for project in db.query(Project).all():
        p = cast(Any, project)
        project_days = weekday_indices(p.working_days)
        holidays = set(p.holidays or [])
        members = {cast(Any, member).id: member for member in project_members(p.id, db)}
        for task in db.query(Task).filter(Task.project_id == p.id).order_by(Task.task_order).all():
            t = cast(Any, task)
            t.category = normalize_category(t.category or t.phase)
            if db.query(TaskDailyAllocation.task_id).filter(TaskDailyAllocation.task_id == t.id).first():
                continue
            assignment = db.get(TaskAssignment, t.id)
            member = members.get(cast(Any, assignment).member_id) if assignment else None
            if not member or not t.start_date or not t.end_date:
                continue
            m = cast(Any, member)
            try:
                cursor = date.fromisoformat(t.start_date)
                end_date = date.fromisoformat(t.end_date)
            except ValueError:
                continue
            member_days = weekday_indices(m.working_days or p.working_days)
            leave_dates = set(m.leave_dates or [])
            capacity = m.hours_per_day * m.allocation / 100
            remaining = t.effort_hours
            allocations_by_day = {}
            while cursor <= end_date and remaining > 0:
                day = cursor.isoformat()
                available = (
                    cursor.weekday() in project_days & member_days
                    and day not in holidays
                    and day not in leave_dates
                    and (not m.available_from or day >= m.available_from)
                    and (not m.available_until or day <= m.available_until)
                )
                if available:
                    if (t.id, day) in calendar:
                        cursor += timedelta(days=1)
                        continue
                    already_used = 0.0
                    for (allocated_task, allocated_day), value in calendar.items():
                        if allocated_day != day:
                            continue
                        allocated_task_obj = db.get(Task, allocated_task)
                        allocated_assignment = db.get(TaskAssignment, allocated_task)
                        if (
                            allocated_task_obj is not None
                            and cast(Any, allocated_task_obj).project_id == p.id
                            and allocated_assignment is not None
                            and cast(Any, allocated_assignment).member_id == m.id
                        ):
                            already_used += value
                    hours = min(remaining, max(0.0, capacity - already_used))
                    if hours:
                        allocations_by_day[day] = allocations_by_day.get(day, 0.0) + hours
                        calendar[(t.id, day)] = hours
                        remaining -= hours
                cursor += timedelta(days=1)
            if remaining <= 0.001:
                for day, hours in allocations_by_day.items():
                    pending_allocations[(t.id, day)] = TaskDailyAllocation(task_id=t.id, work_date=day, allocated_hours=hours)
    db.add_all(pending_allocations.values())


def initialize_database():
    Base.metadata.create_all(bind=engine)
    columns = {column["name"] for column in inspect(engine).get_columns("projects")}
    member_columns = {column["name"] for column in inspect(engine).get_columns("team_members")}
    task_columns = {column["name"] for column in inspect(engine).get_columns("tasks")}
    with engine.begin() as connection:
        if "status" not in columns:
            connection.exec_driver_sql("ALTER TABLE projects ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'Draft'")
        if "archived" not in columns:
            connection.exec_driver_sql("ALTER TABLE projects ADD COLUMN archived BOOLEAN NOT NULL DEFAULT 0")
        if "is_lead" not in member_columns:
            connection.exec_driver_sql("ALTER TABLE team_members ADD COLUMN is_lead BOOLEAN NOT NULL DEFAULT 0")
            # Existing teams: anyone whose job title already says "lead" keeps edit rights.
            connection.exec_driver_sql("UPDATE team_members SET is_lead = 1 WHERE lower(role) LIKE '%lead%'")
        if "additional_role" not in member_columns:
            connection.exec_driver_sql("ALTER TABLE team_members ADD COLUMN additional_role VARCHAR(128)")
        if "risk_level" not in task_columns:
            connection.exec_driver_sql("ALTER TABLE tasks ADD COLUMN risk_level VARCHAR(16) DEFAULT 'Low'")
        if "risk_note" not in task_columns:
            connection.exec_driver_sql("ALTER TABLE tasks ADD COLUMN risk_note TEXT")
        if "started_at" not in task_columns:
            connection.exec_driver_sql("ALTER TABLE tasks ADD COLUMN started_at VARCHAR(32)")
        if "completed_at" not in task_columns:
            connection.exec_driver_sql("ALTER TABLE tasks ADD COLUMN completed_at VARCHAR(32)")
    db = SessionLocal()
    try:
        for project in db.query(Project).all():
            p = cast(Any, project)
            for snapshot in p.members or []:
                add_member_to_project(p, create_legacy_member(snapshot, db), db)
            legacy_tasks = (p.plan or {}).get("tasks", [])
            if legacy_tasks and not db.query(Task.id).filter(Task.project_id == p.id).first():
                id_map = {str(item.get("id")): f"P{p.id}-{item.get('id')}" for item in legacy_tasks}
                for order, item in enumerate(legacy_tasks):
                    db.add(Task(
                        id=id_map[str(item.get("id"))], project_id=p.id, task_order=order,
                        title=item.get("title", "Legacy task"), description=item.get("description", ""),
                        summary=item.get("summary", ""), 
                        story_ids=item.get("story_ids") or [], source_story=item.get("source_story"),
                        category=item.get("category", "Implementation"), phase=item.get("phase"),
                        effort_hours=float(item.get("effort_hours", 1)), remaining_hours=float(item.get("remaining_hours", item.get("effort_hours", 1))),
                        priority=item.get("priority", "Medium"), required_skills=item.get("required_skills") or [],
                        acceptance_criteria=item.get("acceptance_criteria") or [], start_date=item.get("start_date"),
                        end_date=item.get("end_date"), status=item.get("status", "Pending"), uncertain=bool(item.get("uncertain", False)),
                        rationale=item.get("rationale"), warning=item.get("warning"), manually_edited=bool(item.get("manually_edited", False)),
                    ))
                db.flush()
                for item in legacy_tasks:
                    task_id = id_map[str(item.get("id"))]
                    assignee_id = item.get("assignee_id")
                    if assignee_id:
                        member = db.get(TeamMember, str(assignee_id))
                        if member is not None:
                            add_member_to_project(p, member, db)
                            db.add(
                                TaskAssignment(
                                    task_id=task_id,
                                    member_id=cast(Any, member).id,
                                    assigned_hours=float(item.get("effort_hours", 1)),
                                )
                            )
                    for dependency in item.get("dependencies", []):
                        if str(dependency) in id_map:
                            db.add(TaskDependency(task_id=task_id, depends_on_task_id=id_map[str(dependency)]))
            if legacy_tasks and p.status == "Draft":
                statuses = {item.get("status", "Pending") for item in legacy_tasks}
                p.status = "Completed" if statuses == {"Completed"} else "Active"
        migrate_daily_allocations(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


initialize_database()


@app.get("/api/health")
def health():
    return {"status": "ok", "database": "connected"}


@app.get("/api/estimate-accuracy")
def get_estimate_accuracy(today: str | None = None, db: Session = Depends(get_db)):
    """How long each person really takes compared with the plan (feeds the Estimate Coach card)."""
    return accuracy_report(db, parse_today(today))


@app.get("/api/team-workload")
def get_team_workload(db: Session = Depends(get_db)):
    """Hours each person has on each active project, for the Team Info chart."""
    members = db.query(TeamMember).order_by(TeamMember.name).all()
    rows = db.query(TaskAssignment.member_id, Project.id, Project.name, Task.effort_hours, Task.status).join(
        Task, Task.id == TaskAssignment.task_id,
    ).join(Project, Project.id == Task.project_id).filter(Project.archived.is_(False)).all()
    per_member: dict[str, dict[int, dict]] = {}
    project_names: dict[int, str] = {}
    for member_id, project_id, project_name, hours, status in rows:
        project_names[project_id] = project_name
        entry = per_member.setdefault(member_id, {}).setdefault(project_id, {"hours": 0.0, "done": 0.0})
        entry["hours"] += float(hours or 0)
        if status == "Completed":
            entry["done"] += float(hours or 0)
    result = []
    for member in members:
        m = cast(Any, member)
        by_project = [
            {"project_id": project_id, "name": project_names[project_id], "hours": round(item["hours"], 1), "completed_hours": round(item["done"], 1)}
            for project_id, item in sorted(per_member.get(m.id, {}).items())
        ]
        working_days = len(weekday_indices(m.working_days)) or 5
        result.append({
            "id": m.id, "name": m.name, "role": m.role, "additional_role": m.additional_role, "is_lead": bool(m.is_lead),
            "hours_per_day": m.hours_per_day, "weekly_hours": round(float(m.hours_per_day or 0) * working_days, 1),
            "total_hours": round(sum(item["hours"] for item in by_project), 1), "by_project": by_project,
        })
    projects = [{"id": project_id, "name": name} for project_id, name in sorted(project_names.items())]
    return {"projects": projects, "members": result}


@app.get("/api/team-members")
def list_team_members(db: Session = Depends(get_db)):
    return [member_dict(member) for member in db.query(TeamMember).order_by(TeamMember.name).all()]


@app.get("/api/team-members/{member_id}")
def get_team_member(member_id: str, db: Session = Depends(get_db)):
    member = db.get(TeamMember, member_id)
    if not member:
        raise HTTPException(404, "Team member not found.")
    return member_dict(member)


@app.post("/api/team-members", status_code=201)
def create_team_member(payload: MemberCreate, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude={"id"})
    member_id = payload.id or str(uuid4())
    
    if db.get(TeamMember, member_id):
        raise HTTPException(409, "A team member with this ID already exists.")

    data["is_lead"] = bool(data.get("is_lead")) or has_lead_role(data.get("role"), data.get("additional_role"))
    member = TeamMember(id=member_id, **data)
    db.add(member)
    
    try:
        db.commit()
        db.refresh(member)
        result = member_dict(member)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, f"Database integrity error: {str(error)}")
    except Exception as error:
        db.rollback()
        raise HTTPException(500, f"Database error: {str(error)}")
    join_active_projects(db)  # the newcomer joins existing projects and takes unstarted work they fit
    db.refresh(member)
    return member_dict(member)


SCHEDULING_FIELDS = {"hours_per_day", "working_days", "allocation", "available_from", "available_until", "leave_dates"}


@app.get("/api/team-members/{member_id}/allocations")
def get_member_allocations(member_id: str, db: Session = Depends(get_db)):
    member = get_team_member_or_404(member_id, db)
    m = cast(Any, member)
    rows = db.query(Task, Project).join(TaskAssignment, TaskAssignment.task_id == Task.id).join(
        Project, Project.id == Task.project_id,
    ).filter(TaskAssignment.member_id == member_id, Project.archived.is_(False)).order_by(Project.id, Task.task_order).all()

    projects: dict[int, dict] = {}
    for task, project in rows:
        t, p = cast(Any, task), cast(Any, project)
        entry = projects.setdefault(p.id, {
            "project_id": p.id, "name": p.name, "status": p.status, "start_date": p.start_date, "deadline": p.deadline,
            "task_count": 0, "assigned_hours": 0.0, "remaining_hours": 0.0, "completed_hours": 0.0,
            "first_date": None, "last_date": None, "tasks": [],
        })
        remaining = 0.0 if t.status == "Completed" else float(t.remaining_hours or 0)
        entry["task_count"] += 1
        entry["assigned_hours"] += float(t.effort_hours or 0)
        entry["remaining_hours"] += remaining
        if t.status == "Completed":
            entry["completed_hours"] += float(t.effort_hours or 0)
        if t.start_date and (entry["first_date"] is None or t.start_date < entry["first_date"]):
            entry["first_date"] = t.start_date
        if t.end_date and (entry["last_date"] is None or t.end_date > entry["last_date"]):
            entry["last_date"] = t.end_date
        entry["tasks"].append({
            "id": t.id, "title": t.title, "status": t.status, "priority": t.priority,
            "hours": t.effort_hours, "remaining_hours": remaining, "start_date": t.start_date, "end_date": t.end_date,
        })

    total_assigned = sum(item["assigned_hours"] for item in projects.values())
    for item in projects.values():
        for key in ("assigned_hours", "remaining_hours", "completed_hours"):
            item[key] = round(item[key], 1)
        item["share_percent"] = round(100 * item["assigned_hours"] / total_assigned) if total_assigned else 0

    daily_capacity = round(float(m.hours_per_day or 0) * float(m.allocation or 0) / 100, 2)
    working_days = len(weekday_indices(m.working_days)) or 5
    weekly: dict[str, dict] = {}
    allocation_rows = db.query(TaskDailyAllocation.work_date, TaskDailyAllocation.allocated_hours, Project.id, Project.name).join(
        Task, Task.id == TaskDailyAllocation.task_id,
    ).join(TaskAssignment, TaskAssignment.task_id == Task.id).join(
        Project, Project.id == Task.project_id,
    ).filter(TaskAssignment.member_id == member_id, Project.archived.is_(False)).all()
    for work_date, hours, project_id, project_name in allocation_rows:
        try:
            day = date.fromisoformat(work_date)
        except ValueError:
            continue
        week_start = (day - timedelta(days=day.weekday())).isoformat()
        bucket = weekly.setdefault(week_start, {"week": week_start, "hours": 0.0, "capacity_hours": round(daily_capacity * working_days, 1), "by_project": {}})
        bucket["hours"] += float(hours or 0)
        bucket["by_project"][project_name] = bucket["by_project"].get(project_name, 0.0) + float(hours or 0)
    weekly_rows = []
    for key in sorted(weekly):
        bucket = weekly[key]
        weekly_rows.append({
            "week": key, "hours": round(bucket["hours"], 1), "capacity_hours": bucket["capacity_hours"],
            "by_project": [{"name": name, "hours": round(value, 1)} for name, value in bucket["by_project"].items()],
        })

    return {
        "member": member_dict(member),
        "daily_capacity": daily_capacity,
        "weekly_capacity": round(daily_capacity * working_days, 1),
        "totals": {
            "project_count": len(projects),
            "task_count": sum(item["task_count"] for item in projects.values()),
            "assigned_hours": round(total_assigned, 1),
            "remaining_hours": round(sum(item["remaining_hours"] for item in projects.values()), 1),
            "completed_hours": round(sum(item["completed_hours"] for item in projects.values()), 1),
        },
        "projects": list(projects.values()),
        "weekly": weekly_rows,
    }


@app.patch("/api/team-members/{member_id}")
def update_team_member(member_id: str, payload: MemberUpdate, db: Session = Depends(get_db)):
    member = db.get(TeamMember, member_id)
    if not member:
        raise HTTPException(404, "Team member not found.")
    m = cast(Any, member)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("is_lead") is None:
        changes.pop("is_lead", None)
    if ("role" in changes or "additional_role" in changes) and "is_lead" not in changes:
        changes["is_lead"] = has_lead_role(changes.get("role", m.role), changes.get("additional_role", m.additional_role))
    available_from = changes.get("available_from", m.available_from)
    available_until = changes.get("available_until", m.available_until)
    if available_from and available_until and available_until < available_from:
        raise HTTPException(422, "Availability end date must be on or after the start date.")
    for field, value in changes.items():
        setattr(m, field, value)
    project_ids = [row.project_id for row in db.query(ProjectMember).filter(ProjectMember.member_id == member_id).all()]
    if not (SCHEDULING_FIELDS & changes.keys()):
        project_ids = []
    try:
        for project_id in project_ids:
            project = db.get(Project, project_id)
            if project is not None:
                reschedule_project(project, db)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(500, "The team member update and affected schedules could not be saved.") from error
    db.refresh(member)
    return member_dict(member)


@app.delete("/api/team-members/{member_id}", status_code=204)
def delete_team_member(member_id: str, db: Session = Depends(get_db)):
    member = db.get(TeamMember, member_id)
    if not member:
        raise HTTPException(404, "Team member not found.")
    if db.query(TaskAssignment).filter(TaskAssignment.member_id == member_id).first():
        raise HTTPException(409, "This member is assigned to saved tasks. Reassign those tasks before deleting the member.")
    db.query(ProjectMember).filter(ProjectMember.member_id == member_id).delete(synchronize_session=False)
    db.delete(member)
    db.commit()


@app.post("/api/projects", status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    if payload.deadline and payload.deadline < payload.start_date:
        raise HTTPException(422, "Target deadline must be on or after the project start date.")
    project_data = payload.model_dump(exclude={"members", "member_ids"})
    project_data["members"] = [member.model_dump() for member in payload.members]
    project = Project(**project_data)
    db.add(project)
    db.flush()
    p = cast(Any, project)
    member_ids = set(payload.member_ids)
    for item in payload.members:
        member_id = item.id or str(uuid4())
        member = db.get(TeamMember, member_id) or create_legacy_member({**item.model_dump(), "id": member_id}, db)
        add_member_to_project(p, member, db)
        member_ids.add(cast(Any, member).id)
    db.flush()
    missing = [member_id for member_id in member_ids if not db.get(TeamMember, member_id)]
    if missing:
        db.rollback()
        raise HTTPException(422, f"Unknown team member IDs: {', '.join(missing)}.")
    for member_id in member_ids:
        member = db.get(TeamMember, member_id)
        if member is None:
            db.rollback()
            raise HTTPException(422, f"Unknown team member ID: {member_id}.")
        add_member_to_project(p, member, db)
    try:
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(500, "The project could not be saved.") from error
    db.refresh(project)
    return project_dict(p, db)


@app.get("/api/projects")
def list_projects(archived: bool | None = None, db: Session = Depends(get_db)):
    query = db.query(Project)
    if archived is None:
        query = query.filter(Project.archived.is_(False), Project.status != "Draft", Project.plan.is_not(None))
    else:
        query = query.filter(Project.archived.is_(archived), Project.status != "Draft", Project.plan.is_not(None))
    projects = query.order_by(Project.updated_at.desc(), Project.id.desc()).all()
    return [project_dict(p, db, include_plan=False) for p in unique_named_projects(projects)]


@app.get("/api/projects/{project_id}")
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    return project_dict(project, db)


@app.patch("/api/projects/{project_id}")
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    p = cast(Any, project)
    changes = payload.model_dump(exclude_unset=True)
    deadline = changes.get("deadline", p.deadline)
    if deadline and deadline < p.start_date:
        raise HTTPException(422, "Target deadline must be on or after the project start date.")
    for field, value in changes.items():
        setattr(p, field, value)
    db.commit()
    db.refresh(project)
    return project_dict(p, db)


@app.delete("/api/projects/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    delete_project_tasks(db, project_id)
    db.query(ProjectMember).filter(ProjectMember.project_id == project_id).delete(synchronize_session=False)
    db.delete(project)
    db.commit()


@app.post("/api/projects/{project_id}/archive")
def archive_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    p = cast(Any, project)
    p.archived = True
    db.commit()
    return project_dict(p, db, include_plan=False)


@app.post("/api/projects/{project_id}/restore")
def restore_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    p = cast(Any, project)
    p.archived = False
    db.commit()
    return project_dict(p, db, include_plan=False)


async def parse_document_upload(file: UploadFile):
    filename = Path(file.filename or "upload").name
    if re.search(r"[**\\\**/**\x00**]", filename):
        raise HTTPException(400, "Invalid filename.")
    content = await file.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "The uploaded file exceeds the 10 MB limit.")
    try:
        text = extract_text(filename, content)
        stories = extract_stories(text)
    except (ValueError, UnicodeError) as error:
        raise HTTPException(422, str(error)) from error
    if not stories:
        raise HTTPException(422, "No usable requirements were found. Add readable user stories or requirement sentences.")
    return filename, content, text, stories


@app.post("/api/documents/preview")
async def preview_document(file: UploadFile = File(...)):
    filename, content, text, stories = await parse_document_upload(file)
    return {"filename": filename[:255], "bytes": len(content), "stories": stories, "preview": text[:4000]}


@app.post("/api/projects/{project_id}/documents")
async def upload_document(project_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    p = cast(Any, project)
    filename, content, text, stories = await parse_document_upload(file)
    p.document_name = filename[:255]
    p.document_text = text
    p.stories = stories
    p.plan = None
    p.status = "Draft"
    delete_project_tasks(db, project_id)
    db.commit()
    return {"filename": p.document_name, "bytes": len(content), "stories": stories, "preview": text[:4000]}


@app.get("/api/projects/{project_id}/stories")
def get_stories(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    p = cast(Any, project)
    return p.stories


@app.post("/api/projects/{project_id}/team-members")
def add_member(project_id: int, payload: MemberCreate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    member_id = payload.id or str(uuid4())
    member = db.get(TeamMember, member_id)
    if member is None:
        member_data = payload.model_dump(exclude={"id"})
        member_data["is_lead"] = bool(member_data.get("is_lead")) or has_lead_role(member_data.get("role"), member_data.get("additional_role"))
        member = TeamMember(id=member_id, **member_data)
        db.add(member)
        db.flush()
    add_member_to_project(project, member, db)
    db.commit()
    return [member_dict(item) for item in project_members(project_id, db)]


@app.get("/api/projects/{project_id}/team-members")
def get_project_members(project_id: int, db: Session = Depends(get_db)):
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found.")
    return [member_dict(member) for member in project_members(project_id, db)]


@app.post("/api/projects/{project_id}/generate-plan")
def create_plan(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    p = cast(Any, project)
    if not p.stories:
        raise HTTPException(422, "Upload a readable user story document before generating a plan.")
    # Plans are built for the whole team as it is now, including people who joined after the project was created.
    for team_member in db.query(TeamMember).all():
        add_member_to_project(p, team_member, db)
    db.flush()
    members = [member_dict(member) for member in project_members(project_id, db)]
    if not members:
        raise HTTPException(422, "Add at least one team member before generating a plan.")
    project_data = {column.name: getattr(p, column.name) for column in Project.__table__.columns}
    
    generated = generate_plan({**project_data, "members": members}, p.stories, other_project_bookings(db, p.id), calibration=build_calibration(db))

    id_map = {task["id"]: f"P{p.id}-{task['id']}" for task in generated["tasks"]}
    saved_tasks = [Task(
        id=id_map[item["id"]], project_id=p.id, task_order=order, title=item["title"],
        description=item["description"], summary=item.get("summary", ""), 
        story_ids=item.get("story_ids", []), source_story=item.get("source_story"),
        category=normalize_category(item["category"]), phase=item.get("phase"), effort_hours=item["effort_hours"],
        remaining_hours=item["remaining_hours"], priority=item["priority"], required_skills=item.get("required_skills", []),
        acceptance_criteria=item.get("acceptance_criteria", []), start_date=item.get("start_date"), end_date=item.get("end_date"),
        status=item["status"], uncertain=item.get("uncertain", False), rationale=item.get("rationale"), warning=item.get("warning"),
        risk_level=item.get("risk_level", "Low"), risk_note=item.get("risk_note"),
    ) for order, item in enumerate(generated["tasks"])]
    try:
        delete_project_tasks(db, p.id)
        db.add_all(saved_tasks)
        db.flush()
        for item in generated["tasks"]:
            task_id = id_map[item["id"]]
            assignee_id = item.get("assignee_id")
            if assignee_id:
                assignee = db.get(TeamMember, assignee_id)
                if assignee is not None:
                    db.add(
                        TaskAssignment(
                            task_id=task_id,
                            member_id=cast(Any, assignee).id,
                            assigned_hours=item["effort_hours"],
                        )
                    )
            for dependency_id in item.get("dependencies", []):
                if dependency_id in id_map:
                    db.add(TaskDependency(task_id=task_id, depends_on_task_id=id_map[dependency_id]))
            for allocation in item.get("daily_allocations", []):
                db.add(TaskDailyAllocation(task_id=task_id, work_date=allocation["date"], allocated_hours=allocation["hours"]))
        generated["tasks"] = [{
            **item,
            "id": id_map[item["id"]],
            "dependencies": [id_map[value] for value in item.get("dependencies", []) if value in id_map],
        } for item in generated["tasks"]]
        p.plan = generated
        p.status = "Active"
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(500, "The plan and its tasks could not be saved; no partial plan was retained.") from error
    db.refresh(p)
    try:
        plan_start = date.fromisoformat(p.start_date)
    except ValueError:
        plan_start = date.today()
    store_forecast(p, db, plan_start)
    db.refresh(p)
    return project_plan(p, db)


@app.get("/api/projects/{project_id}/plan")
def get_plan(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    plan = project_plan(project, db)
    if not plan:
        raise HTTPException(404, "No plan has been generated yet.")
    return plan


@app.get("/api/projects/{project_id}/tasks")
def get_project_tasks(project_id: int, db: Session = Depends(get_db)):
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found.")
    return [task_dict(task, db) for task in db.query(Task).filter(Task.project_id == project_id).order_by(Task.task_order).all()]


def reschedule_project(project: Project, db: Session):
    p = cast(Any, project)
    members = [member_dict(member) for member in project_members(p.id, db)]
    assignment_by_task = {
        cast(Any, assignment).task_id: cast(Any, assignment).member_id
        for assignment in db.query(TaskAssignment).join(Task).filter(Task.project_id == p.id).all()
    }
    tasks = db.query(Task).filter(Task.project_id == p.id).order_by(Task.task_order).all()
    tasks_by_id = {cast(Any, task).id: task for task in tasks}
    for assignment in db.query(TaskAssignment).join(Task).filter(Task.project_id == p.id).all():
        cast(Any, assignment).assigned_hours = cast(Any, tasks_by_id[cast(Any, assignment).task_id]).effort_hours
    task_inputs = []
    for task in tasks:
        t = cast(Any, task)
        dependencies = [row.depends_on_task_id for row in db.query(TaskDependency).filter(TaskDependency.task_id == t.id).all()]
        task_inputs.append({
            "id": t.id,
            "title": t.title,
            "assignee_id": assignment_by_task.get(t.id),
            "effort_hours": t.effort_hours,
            "dependencies": dependencies,
            "requested_start_date": t.start_date,
        })
    project_data = {column.name: getattr(p, column.name) for column in Project.__table__.columns}
    try:
        scheduled = reschedule_tasks(project_data, members, task_inputs, other_project_bookings(db, p.id))
    except ValueError as error:
        raise HTTPException(422, str(error)) from error

    for task, item in zip(tasks, scheduled):
        t = cast(Any, task)
        t.start_date = item.get("start_date")
        t.end_date = item.get("end_date")
        t.warning = item.get("warning")
    task_ids = [cast(Any, task).id for task in tasks]
    if task_ids:
        db.query(TaskDailyAllocation).filter(TaskDailyAllocation.task_id.in_(task_ids)).delete(synchronize_session=False)
    for task, item in zip(tasks, scheduled):
        for allocation in item.get("daily_allocations", []):
            db.add(TaskDailyAllocation(task_id=cast(Any, task).id, work_date=allocation["date"], allocated_hours=allocation["hours"]))


@app.patch("/api/tasks/{task_id}")
def update_task(task_id: str, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found.")
    t = cast(Any, task)
    changes = payload.model_dump(exclude_unset=True)
    reschedule_needed = bool({"assignee_id", "effort_hours", "start_date"} & changes.keys())
    if changes.get("status") and changes["status"] not in {"Pending", "In Progress", "Completed", "Blocked"}:
        raise HTTPException(422, "Status must be Pending, In Progress, Completed, or Blocked.")
    if "assignee_id" in changes:
        member_id = changes.pop("assignee_id")
        if member_id and not db.get(ProjectMember, (t.project_id, member_id)):
            raise HTTPException(422, "Assignee must be a member of this project.")
        assignment = db.get(TaskAssignment, t.id)
        if member_id:
            if assignment:
                cast(Any, assignment).member_id = member_id
            else:
                db.add(TaskAssignment(task_id=t.id, member_id=member_id, assigned_hours=t.effort_hours))
        elif assignment:
            db.delete(assignment)
    for field, value in changes.items():
        setattr(t, field, value)
    if "status" in changes:
        # Keep the hours in step with progress so remaining work and the allocations view stay truthful.
        if changes["status"] == "Completed":
            t.remaining_hours = 0.0
        elif not t.remaining_hours:
            t.remaining_hours = t.effort_hours
        # Timestamps feed the weekly report and the Estimate Coach (planned vs actual duration).
        moment = datetime.now().isoformat(timespec="seconds")
        if changes["status"] == "In Progress" and not t.started_at:
            t.started_at = moment
        elif changes["status"] == "Completed":
            t.started_at = t.started_at or moment
            t.completed_at = moment
        elif t.completed_at:
            t.completed_at = None
    if reschedule_needed or set(changes) - {"status"}:
        t.manually_edited = True
    project = db.get(Project, t.project_id)
    if project is None:
        db.rollback()
        raise HTTPException(404, "Project not found for this task.")
    p = cast(Any, project)
    try:
        if reschedule_needed:
            db.flush()
            reschedule_project(p, db)
        statuses = [cast(Any, item).status for item in db.query(Task).filter(Task.project_id == t.project_id).all()]
        p.status = "Completed" if statuses and all(value == "Completed" for value in statuses) else "Active"
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(500, "The task update and schedule could not be saved.") from error
    return task_dict(t, db)


@app.get("/api/projects/{project_id}/dashboard")
def dashboard(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    plan = project_plan(project, db)
    if not plan:
        raise HTTPException(404, "Generate a plan before viewing the dashboard.")
    p = cast(Any, project)
    return {"project": {"id": p.id, "name": p.name, "deadline": p.deadline}, **plan}


def plan_inputs(project: Project, db: Session):
    """Task dicts (assignee, dependencies, hours, status, dates) used by the re-plan and forecast tools."""
    p = cast(Any, project)
    assignee_by_task = {
        cast(Any, row).task_id: cast(Any, row).member_id
        for row in db.query(TaskAssignment).join(Task).filter(Task.project_id == p.id).all()
    }
    inputs = []
    for task in db.query(Task).filter(Task.project_id == p.id).order_by(Task.task_order).all():
        t = cast(Any, task)
        inputs.append({
            "id": t.id, "title": t.title, "phase": t.phase, "status": t.status, "priority": t.priority,
            "assignee_id": assignee_by_task.get(t.id), "effort_hours": t.effort_hours, "remaining_hours": t.remaining_hours,
            "dependencies": [row.depends_on_task_id for row in db.query(TaskDependency).filter(TaskDependency.task_id == t.id).all()],
            "start_date": t.start_date, "end_date": t.end_date, "uncertain": bool(t.uncertain), "risk_level": t.risk_level,
        })
    return inputs


def parse_today(value: str | None) -> date:
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise HTTPException(422, "today must look like 2026-11-02.") from error


def compute_impact(project: Project, db: Session, today: date):
    p = cast(Any, project)
    members = [member_dict(member) for member in project_members(p.id, db)]
    names = {member["id"]: member["name"] for member in members}
    inputs = plan_inputs(p, db)
    project_data = {column.name: getattr(p, column.name) for column in Project.__table__.columns}
    results = replan_from(project_data, members, inputs, today, other_project_bookings(db, p.id))

    today_iso = today.isoformat()
    overdue = [item for item in inputs if item["status"] != "Completed" and item["end_date"] and item["end_date"] < today_iso]
    blocked = [item for item in inputs if item["status"] == "Blocked"]
    shifted = []
    for before, after in zip(inputs, results):
        if before["status"] == "Completed" or not after.get("replanned") or not before["end_date"]:
            continue
        delta = (date.fromisoformat(after["end_date"]) - date.fromisoformat(before["end_date"])).days
        if delta or after["start_date"] != before["start_date"]:
            shifted.append({
                "id": before["id"], "title": before["title"], "status": before["status"],
                "assignee_name": names.get(before["assignee_id"]),
                "old_start": before["start_date"], "new_start": after["start_date"],
                "old_end": before["end_date"], "new_end": after["end_date"], "delta_days": delta,
            })
    old_ends = [item["end_date"] for item in inputs if item["end_date"]]
    new_ends = [item["end_date"] for item in results if item.get("end_date")]
    original_finish = max(old_ends) if old_ends else None
    replanned_finish = max(new_ends) if new_ends else None
    slip = (date.fromisoformat(replanned_finish) - date.fromisoformat(original_finish)).days if original_finish and replanned_finish else 0
    deadline = p.deadline
    return {
        "today": today_iso,
        "overdue": [{"id": i["id"], "title": i["title"], "end_date": i["end_date"], "assignee_name": names.get(i["assignee_id"])} for i in overdue],
        "blocked": [{"id": i["id"], "title": i["title"], "end_date": i["end_date"], "assignee_name": names.get(i["assignee_id"])} for i in blocked],
        "original_finish": original_finish,
        "replanned_finish": replanned_finish,
        "slip_days": slip,
        "deadline": deadline,
        "deadline_ok": (replanned_finish <= deadline) if (deadline and replanned_finish) else None,
        "deadline_ok_before": (original_finish <= deadline) if (deadline and original_finish) else None,
        "shifted_tasks": shifted,
        "people_affected": sorted({item["assignee_name"] for item in shifted if item["assignee_name"]}),
        "needs_replan": bool(overdue or blocked or any(item["delta_days"] > 0 for item in shifted)),
        "unfinished_tasks": sum(1 for item in inputs if item["status"] != "Completed"),
    }, results


def compute_forecast(project: Project, db: Session, today: date, runs: int = DEFAULT_RUNS):
    p = cast(Any, project)
    members = [member_dict(member) for member in project_members(p.id, db)]
    project_data = {column.name: getattr(p, column.name) for column in Project.__table__.columns}
    return forecast_plan(project_data, members, plan_inputs(p, db), today, other_project_bookings(db, p.id), runs=runs, seed=int(p.id))


def store_forecast(project: Project, db: Session, today: date):
    """Keep the headline forecast numbers (and a risk when the odds are poor) on the stored plan summary."""
    p = cast(Any, project)
    try:
        forecast = compute_forecast(p, db, today)
        plan = dict(p.plan or {})
        plan["summary"] = attach_to_summary(dict(plan.get("summary") or {}), forecast)
        p.plan = plan
        db.commit()
    except Exception:  # a forecast must never make plan generation fail
        db.rollback()


@app.get("/api/projects/{project_id}/forecast")
def get_forecast(project_id: int, today: str | None = None, runs: int = DEFAULT_RUNS, db: Session = Depends(get_db)):
    """Chance of finishing on time, from many simulated runs of the remaining work."""
    project = get_project_or_404(project_id, db)
    if not db.query(Task.id).filter(Task.project_id == project_id).first():
        raise HTTPException(404, "Generate a plan before asking for a forecast.")
    return compute_forecast(project, db, parse_today(today), runs=max(20, min(runs, 1000)))


def weekly_report_for(project_id: int, week: str | None, today: str | None, db: Session):
    project = get_project_or_404(project_id, db)
    p = cast(Any, project)
    plan = project_plan(p, db)
    if not plan:
        raise HTTPException(404, "Generate a plan before asking for a report.")
    current = parse_today(today)
    try:
        any_day = date.fromisoformat(week) if week else current
    except ValueError as error:
        raise HTTPException(422, "week must look like 2026-11-02.") from error
    summary = plan.get("summary") or {}
    return build_report({"name": p.name, "deadline": p.deadline}, plan["tasks"], summary, any_day, current)


@app.get("/api/projects/{project_id}/report")
def get_weekly_report(project_id: int, week: str | None = None, today: str | None = None, db: Session = Depends(get_db)):
    """A ready-to-send weekly status report. `week` is any date inside the week wanted (default: this week)."""
    return weekly_report_for(project_id, week, today, db)


@app.get("/api/projects/{project_id}/report/export")
def export_weekly_report(project_id: int, format: str = "pdf", week: str | None = None, today: str | None = None, db: Session = Depends(get_db)):
    """The same report as a downloadable Word (.docx), PDF or CSV file."""
    fmt = format.lower().lstrip(".")
    if fmt not in EXPORT_FORMATS:
        raise HTTPException(422, "format must be docx, pdf or csv.")
    report = weekly_report_for(project_id, week, today, db)
    data, media, extension = export_report(report, fmt)
    name = re.sub(r"[^a-z0-9]+", "-", str(report["project"]).lower()).strip("-") or "project"
    filename = f"weekly-report-{name}-{report['week_start']}.{extension}"
    return Response(content=data, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def rebalance_inputs(project: Project, db: Session):
    """plan_inputs plus what the rebalance needs: required skills and each task's daily hours."""
    p = cast(Any, project)
    tasks = plan_inputs(p, db)
    skills = {row.id: (row.required_skills or []) for row in db.query(Task.id, Task.required_skills).filter(Task.project_id == p.id).all()}
    allocations: dict[str, list[dict]] = {}
    for task_id, work_date, hours in db.query(
        TaskDailyAllocation.task_id, TaskDailyAllocation.work_date, TaskDailyAllocation.allocated_hours,
    ).join(Task, Task.id == TaskDailyAllocation.task_id).filter(Task.project_id == p.id).all():
        allocations.setdefault(task_id, []).append({"date": work_date, "hours": hours})
    for item in tasks:
        item["required_skills"] = skills.get(item["id"], [])
        item["daily_allocations"] = allocations.get(item["id"], [])
    return tasks


def rebalance_project(project: Project, db: Session, today: date):
    """Bring every team member into the project and give newcomers (people with no work on it) unstarted tasks."""
    p = cast(Any, project)
    outcome = {"added_members": [], "moved": [], "rescheduled": 0}
    if not db.query(Task.id).filter(Task.project_id == p.id).first():
        return outcome

    on_project = {cast(Any, member).id for member in project_members(p.id, db)}
    for member in db.query(TeamMember).order_by(TeamMember.name).all():
        if cast(Any, member).id not in on_project:
            add_member_to_project(p, member, db)
            outcome["added_members"].append(cast(Any, member).name)
    db.flush()

    members = [member_dict(member) for member in project_members(p.id, db)]
    names = {member["id"]: member["name"] for member in members}
    inputs = rebalance_inputs(p, db)
    project_data = {column.name: getattr(p, column.name) for column in Project.__table__.columns}
    results, _newcomers = rebalance_unstarted(project_data, members, inputs, today, other_project_bookings(db, p.id), calibration=build_calibration(db, today))
    moved = [(before, after) for before, after in zip(inputs, results) if after.get("moved")]
    if not moved:
        db.commit()  # keep the new memberships even when nobody takes work
        return outcome

    changed = [item for item in results if item.get("replanned")]
    db.query(TaskDailyAllocation).filter(TaskDailyAllocation.task_id.in_([item["id"] for item in changed])).delete(synchronize_session=False)
    for item in changed:
        t = cast(Any, db.get(Task, item["id"]))
        t.start_date, t.end_date = item["start_date"], item["end_date"]
        t.effort_hours, t.remaining_hours, t.warning = item["effort_hours"], item["remaining_hours"], item.get("warning")
        assignment = db.get(TaskAssignment, t.id)
        if assignment is None:
            db.add(TaskAssignment(task_id=t.id, member_id=item["assignee_id"], assigned_hours=item["effort_hours"]))
        else:
            cast(Any, assignment).member_id = item["assignee_id"]
            cast(Any, assignment).assigned_hours = item["effort_hours"]
        if item.get("moved"):
            t.rationale = f"Handed to {item['assignee_name']} when they joined the project: they had no work on it and are the best fit for this task."
        for allocation in item["daily_allocations"]:
            db.add(TaskDailyAllocation(task_id=t.id, work_date=allocation["date"], allocated_hours=allocation["hours"]))
    for before, after in moved:
        outcome["moved"].append({"id": after["id"], "title": after["title"], "from": names.get(before.get("assignee_id")), "to": after["assignee_name"]})
    outcome["rescheduled"] = len(changed)

    plan = dict(p.plan or {})
    summary = dict(plan.get("summary") or {})
    finishes = [item["end_date"] for item in results if item.get("end_date")]
    if finishes:
        summary["projected_completion"] = max(finishes)
        if p.deadline:
            summary["deadline_feasible"] = max(finishes) <= p.deadline
    plan["summary"] = summary
    p.plan = plan
    db.commit()
    db.refresh(p)
    store_forecast(p, db, today)
    return outcome


def join_active_projects(db: Session):
    """A new team member joins every active project and takes unstarted work they are the best fit for."""
    today = date.today()
    for project in db.query(Project).filter(Project.archived.is_(False)).all():
        try:
            rebalance_project(project, db, today)
        except Exception:  # one project failing must never block adding the person
            db.rollback()


@app.post("/api/projects/{project_id}/rebalance")
def rebalance_endpoint(project_id: int, today: str | None = None, db: Session = Depends(get_db)):
    """Add every team member to this project and hand newcomers the unstarted tasks they fit best."""
    project = get_project_or_404(project_id, db)
    if cast(Any, project).archived:
        raise HTTPException(409, "Restore this project before assigning new members.")
    return rebalance_project(project, db, parse_today(today))


@app.get("/api/projects/{project_id}/impact")
def get_delay_impact(project_id: int, today: str | None = None, db: Session = Depends(get_db)):
    """Read-only: what would happen if the unfinished work were re-planned from today?"""
    project = get_project_or_404(project_id, db)
    impact, _results = compute_impact(project, db, parse_today(today))
    return impact


@app.post("/api/projects/{project_id}/replan")
def replan_project(project_id: int, today: str | None = None, db: Session = Depends(get_db)):
    """Save the re-plan: unfinished tasks get new dates and daily hours; completed tasks and assignees are untouched."""
    project = get_project_or_404(project_id, db)
    p = cast(Any, project)
    if p.archived:
        raise HTTPException(409, "Restore this project before re-planning it.")
    impact, results = compute_impact(project, db, parse_today(today))
    changed = [item for item in results if item.get("replanned")]
    try:
        task_ids = [item["id"] for item in changed]
        if task_ids:
            db.query(TaskDailyAllocation).filter(TaskDailyAllocation.task_id.in_(task_ids)).delete(synchronize_session=False)
        for item in results:
            task = db.get(Task, item["id"])
            if task is None or item["status"] == "Completed":
                continue
            t = cast(Any, task)
            if item.get("replanned"):
                t.start_date, t.end_date = item["start_date"], item["end_date"]
                for allocation in item["daily_allocations"]:
                    db.add(TaskDailyAllocation(task_id=t.id, work_date=allocation["date"], allocated_hours=allocation["hours"]))
            t.warning = item.get("warning")
        plan = dict(p.plan or {})
        summary = dict(plan.get("summary") or {})
        summary["projected_completion"] = impact["replanned_finish"]
        if impact["deadline_ok"] is not None:
            summary["deadline_feasible"] = impact["deadline_ok"]
        plan["summary"] = summary
        p.plan = plan
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(500, "The re-plan could not be saved; nothing was changed.") from error
    db.refresh(p)
    store_forecast(p, db, parse_today(today))
    db.refresh(p)
    return project_plan(p, db)


UPCOMING_DEADLINE_LIMIT = 100


def unique_named_projects(projects, limit=5):
    unique = []
    seen_names = set()
    for project in projects:
        p = cast(Any, project)
        key = re.sub(r"\s+", " ", p.name).strip().casefold()
        if key in seen_names:
            continue
        seen_names.add(key)
        unique.append(p)
        if len(unique) == limit:
            break
    return unique


@app.get("/api/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    projects = db.query(Project).all()
    active_projects = [project for project in projects if not cast(Any, project).archived]
    tasks = []
    for task in db.query(Task).all():
        task_project = db.get(Project, cast(Any, task).project_id)
        if task_project is not None and not cast(Any, task_project).archived:
            tasks.append(task)
    members = db.query(TeamMember).order_by(TeamMember.name).all()
    task_statuses = ("Pending", "In Progress", "Completed", "Blocked")
    task_counts = {status: sum(cast(Any, task).status == status for task in tasks) for status in task_statuses}
    project_counts = {
        "Draft": sum(cast(Any, project).status == "Draft" for project in active_projects),
        "Active": sum(cast(Any, project).status == "Active" for project in active_projects),
        "Completed": sum(cast(Any, project).status == "Completed" for project in active_projects),
        "Archived": sum(cast(Any, project).archived for project in projects),
    }
    today = date.today().isoformat()
    overdue = sum(bool(cast(Any, task).end_date and cast(Any, task).end_date < today and cast(Any, task).status != "Completed") for task in tasks)
    recent = db.query(Project).filter(
        Project.archived.is_(False),
        Project.status != "Draft",
        Project.plan.is_not(None),
    ).order_by(Project.updated_at.desc(), Project.id.desc()).all()
    recent = unique_named_projects(recent)
    recent_projects = []
    for project in recent:
        p = cast(Any, project)
        plan = project_plan(p, db)
        recent_projects.append({
            "id": p.id,
            "name": p.name,
            "status": "Archived" if p.archived else p.status,
            "deadline": p.deadline,
            "project_type": p.project_type,
            "task_count": plan["summary"]["task_count"] if plan else 0,
            "progress_percent": plan["summary"]["progress_percent"] if plan else 0,
            "risk_level": (plan["summary"].get("risk_level") if plan else None) or "Low",
        })
    upcoming = db.query(Project).filter(
        Project.archived.is_(False),
        Project.plan.is_not(None),
        Project.deadline.is_not(None),
        Project.deadline >= today,
        Project.status != "Completed",
    ).order_by(Project.deadline, Project.updated_at.desc(), Project.id.desc()).all()
    upcoming = unique_named_projects(upcoming, limit=UPCOMING_DEADLINE_LIMIT)
    team_workload = []
    for member in members:
        m = cast(Any, member)
        assigned = sum(cast(Any, row).assigned_hours for row in db.query(TaskAssignment).join(Task).join(Project).filter(TaskAssignment.member_id == m.id, Project.archived.is_(False)).all())
        team_workload.append({"id": m.id, "name": m.name, "hours": round(assigned, 1), "allocation": m.allocation})
    weekly = {}
    for task in tasks:
        t = cast(Any, task)
        if not t.start_date:
            continue
        try:
            start = date.fromisoformat(t.start_date)
        except ValueError:
            continue
        week_start = (start - timedelta(days=start.weekday())).isoformat()
        bucket = weekly.setdefault(week_start, {"week": week_start, "planned": 0.0, "completed": 0.0})
        bucket["planned"] += t.effort_hours
        if t.status == "Completed":
            bucket["completed"] += t.effort_hours
    return {
        "metrics": {
            "total_projects": len(projects),
            "active_projects": project_counts["Active"],
            "completed_projects": project_counts["Completed"],
            "team_members": len(members),
            "tasks_in_progress": task_counts["In Progress"],
            "overdue_tasks": overdue,
        },
        "project_status": [{"name": name, "value": value} for name, value in project_counts.items()],
        "task_progress": [{"name": name, "value": value} for name, value in task_counts.items()],
        "team_workload": team_workload,
        "project_timeline": [weekly[key] for key in sorted(weekly)],
        "recent_projects": recent_projects,
        "upcoming_deadlines": [{"id": p.id, "name": p.name, "deadline": p.deadline, "status": p.status} for p in upcoming],
    }


@app.get("/api/calendar")
def get_calendar(month: str | None = None, db: Session = Depends(get_db)):
    """Project starts, deadlines and task due dates for one month (YYYY-MM)."""
    month = month or date.today().strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise HTTPException(422, "month must look like 2026-11.")
    events = []
    projects = db.query(Project).filter(Project.archived.is_(False), Project.status != "Draft", Project.plan.is_not(None)).all()
    for project in projects:
        p = cast(Any, project)
        if p.start_date and p.start_date.startswith(month):
            events.append({"date": p.start_date, "type": "project_start", "title": f"{p.name} starts", "project_id": p.id, "project_name": p.name, "status": p.status})
        if p.deadline and p.deadline.startswith(month):
            events.append({"date": p.deadline, "type": "deadline", "title": f"{p.name} deadline", "project_id": p.id, "project_name": p.name, "status": p.status})
    rows = db.query(Task, Project).join(Project, Project.id == Task.project_id).filter(
        Project.archived.is_(False), Task.end_date.like(f"{month}%"), Task.status != "Completed",
    ).all()
    for task, project in rows:
        t, p = cast(Any, task), cast(Any, project)
        assignment = db.get(TaskAssignment, t.id)
        assignee = db.get(TeamMember, cast(Any, assignment).member_id) if assignment else None
        events.append({
            "date": t.end_date, "type": "task_due", "title": t.title, "project_id": p.id, "project_name": p.name,
            "status": t.status, "priority": t.priority, "assignee_name": cast(Any, assignee).name if assignee else None,
        })
    events.sort(key=lambda item: (item["date"], item["type"]))
    return {"month": month, "events": events}


@app.get("/api/projects/{project_id}/export")
def export_plan(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    plan = project_plan(project, db) if project else None
    if not project or not plan:
        raise HTTPException(404, "A generated plan was not found.")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id", "title", "story_ids", "category", "effort_hours", "assignee_name", "start_date", "end_date", "status", "dependencies"])
    writer.writeheader()
    for task in plan["tasks"]:
        writer.writerow({**task, "story_ids": ";".join(task["story_ids"]), "dependencies": ";".join(task["dependencies"])})
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="planforge-project-{cast(Any, project).id}.csv"'})