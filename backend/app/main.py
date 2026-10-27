import csv
import io
import os
import re
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine, get_db
from .document_processing import extract_stories, extract_text
from .models import Project, ProjectMember, Task, TaskAssignment, TaskDailyAllocation, TaskDependency, TeamMember
from .planning import generate_plan, normalize_category, reschedule_tasks
from .schemas import MemberCreate, MemberUpdate, ProjectCreate, ProjectUpdate, TaskUpdate

app = FastAPI(title="GenPlan API", version="0.2.0", description="Deterministic, explainable project planning service.")
default_origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:5176",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
    "http://127.0.0.1:5176",
]
origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", ",".join(default_origins)).split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


def member_dict(member: TeamMember):
    return {column.name: getattr(member, column.name) for column in TeamMember.__table__.columns}


def project_members(project_id: int, db: Session):
    return db.query(TeamMember).join(ProjectMember, ProjectMember.member_id == TeamMember.id).filter(ProjectMember.project_id == project_id).order_by(TeamMember.name).all()


def task_dict(task: Task, db: Session):
    assignment = db.get(TaskAssignment, task.id)
    assignee = db.get(TeamMember, assignment.member_id) if assignment else None
    dependencies = [row.depends_on_task_id for row in db.query(TaskDependency).filter(TaskDependency.task_id == task.id).all()]
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "story_ids": task.story_ids or [],
        "source_story": task.source_story,
        "category": normalize_category(task.category or task.phase),
        "phase": task.phase,
        "effort_hours": task.effort_hours,
        "remaining_hours": task.remaining_hours,
        "priority": task.priority,
        "required_skills": task.required_skills or [],
        "acceptance_criteria": task.acceptance_criteria or [],
        "assignee_id": assignee.id if assignee else None,
        "assignee_name": assignee.name if assignee else None,
        "dependencies": dependencies,
        "start_date": task.start_date,
        "end_date": task.end_date,
        "status": task.status,
        "uncertain": task.uncertain,
        "rationale": task.rationale,
        "warning": task.warning,
        "manually_edited": task.manually_edited,
        "daily_allocations": [
            {"date": allocation.work_date, "hours": allocation.allocated_hours}
            for allocation in db.query(TaskDailyAllocation).filter(TaskDailyAllocation.task_id == task.id).order_by(TaskDailyAllocation.work_date).all()
        ],
    }


def project_plan(project: Project, db: Session):
    if not project.plan and not db.query(Task.id).filter(Task.project_id == project.id).first():
        return None
    base = dict(project.plan or {})
    tasks = [task_dict(task, db) for task in db.query(Task).filter(Task.project_id == project.id).order_by(Task.task_order).all()]
    counts = {status: sum(task["status"] == status for task in tasks) for status in ("Pending", "In Progress", "Completed", "Blocked")}
    summary = dict(base.get("summary") or {})
    summary.update({
        "status": project.status,
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
    members = project_members(project.id, db)
    try:
        cursor = date.fromisoformat(project.start_date)
        final_date = date.fromisoformat(project.deadline) if project.deadline else cursor
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

    project_days = weekday_indices(project.working_days)
    holidays = set(project.holidays or [])
    while cursor and final_date and cursor <= final_date:
        if cursor.weekday() in project_days and cursor.isoformat() not in holidays:
            for member in members:
                member_days = weekday_indices(member.working_days or project.working_days)
                leave_dates = set(member.leave_dates or [])
                if cursor.weekday() not in member_days or cursor.isoformat() in leave_dates:
                    continue
                if member.available_from and cursor.isoformat() < member.available_from:
                    continue
                if member.available_until and cursor.isoformat() > member.available_until:
                    continue
                daily_workload[(cursor.isoformat(), member.id)] = {
                    "date": cursor.isoformat(),
                    "member_id": member.id,
                    "member_name": member.name,
                    "capacity_hours": round(member.hours_per_day * member.allocation / 100, 2),
                    "allocated_hours": 0.0,
                    "remaining_hours": round(member.hours_per_day * member.allocation / 100, 2),
                    "tasks": [],
                }
        cursor += timedelta(days=1)

    allocations = db.query(TaskDailyAllocation, Task, TaskAssignment, TeamMember).join(
        Task, Task.id == TaskDailyAllocation.task_id,
    ).join(
        TaskAssignment, TaskAssignment.task_id == Task.id,
    ).join(
        TeamMember, TeamMember.id == TaskAssignment.member_id,
    ).filter(Task.project_id == project.id).order_by(TaskDailyAllocation.work_date, Task.task_order).all()
    for allocation, task, _assignment, member in allocations:
        key = (allocation.work_date, member.id)
        item = daily_workload.setdefault(key, {
            "date": allocation.work_date,
            "member_id": member.id,
            "member_name": member.name,
            "capacity_hours": round(member.hours_per_day * member.allocation / 100, 2),
            "allocated_hours": 0.0,
            "remaining_hours": 0.0,
            "tasks": [],
        })
        item["allocated_hours"] = round(item["allocated_hours"] + allocation.allocated_hours, 2)
        item["tasks"].append({
            "id": task.id,
            "title": task.title,
            "start_date": task.start_date,
            "end_date": task.end_date,
            "effort_hours": task.effort_hours,
            "allocated_hours": allocation.allocated_hours,
            "status": task.status,
        })
    workload_rows = sorted(daily_workload.values(), key=lambda item: (item["date"], item["member_name"]))
    for item in workload_rows:
        item["remaining_hours"] = round(max(0.0, item["capacity_hours"] - item["allocated_hours"]), 2)
    return {
        **base,
        "id": project.id,
        "project_id": project.id,
        "name": project.name,
        "project_type": project.project_type,
        "start_date": project.start_date,
        "deadline": project.deadline,
        "status": project.status,
        "archived": project.archived,
        "stories": base.get("stories", project.stories or []),
        "tasks": tasks,
        "daily_workload": workload_rows,
        "summary": summary,
    }


def project_dict(project: Project, db: Session, include_plan=True):
    result = {column.name: getattr(project, column.name) for column in Project.__table__.columns}
    result["members"] = [member_dict(member) for member in project_members(project.id, db)]
    result["has_plan"] = bool(project.plan or db.query(Task.id).filter(Task.project_id == project.id).first())
    if include_plan:
        result["plan"] = project_plan(project, db)
    else:
        result.pop("plan", None)
        result.pop("members", None)
    return result


def add_member_to_project(project: Project, member: TeamMember, db: Session):
    if not db.get(ProjectMember, (project.id, member.id)):
        db.add(ProjectMember(project_id=project.id, member_id=member.id))


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
        key = (allocation.task_id, allocation.work_date)
        calendar[key] = allocation.allocated_hours
    for project in db.query(Project).all():
        project_days = weekday_indices(project.working_days)
        holidays = set(project.holidays or [])
        members = {member.id: member for member in project_members(project.id, db)}
        for task in db.query(Task).filter(Task.project_id == project.id).order_by(Task.task_order).all():
            task.category = normalize_category(task.category or task.phase)
            if db.query(TaskDailyAllocation.task_id).filter(TaskDailyAllocation.task_id == task.id).first():
                continue
            assignment = db.get(TaskAssignment, task.id)
            member = members.get(assignment.member_id) if assignment else None
            if not member or not task.start_date or not task.end_date:
                continue
            try:
                cursor = date.fromisoformat(task.start_date)
                end_date = date.fromisoformat(task.end_date)
            except ValueError:
                continue
            member_days = weekday_indices(member.working_days or project.working_days)
            leave_dates = set(member.leave_dates or [])
            capacity = member.hours_per_day * member.allocation / 100
            remaining = task.effort_hours
            allocations_by_day = {}
            while cursor <= end_date and remaining > 0:
                day = cursor.isoformat()
                available = (
                    cursor.weekday() in project_days & member_days
                    and day not in holidays
                    and day not in leave_dates
                    and (not member.available_from or day >= member.available_from)
                    and (not member.available_until or day <= member.available_until)
                )
                if available:
                    if (task.id, day) in calendar:
                        cursor += timedelta(days=1)
                        continue
                    already_used = sum(
                        value for (allocated_task, allocated_day), value in calendar.items()
                        if allocated_day == day and db.get(Task, allocated_task).project_id == project.id
                        and db.get(TaskAssignment, allocated_task) is not None
                        and db.get(TaskAssignment, allocated_task).member_id == member.id
                    )
                    hours = min(remaining, max(0.0, capacity - already_used))
                    if hours:
                        allocations_by_day[day] = allocations_by_day.get(day, 0.0) + hours
                        calendar[(task.id, day)] = hours
                        remaining -= hours
                cursor += timedelta(days=1)
            if remaining <= 0.001:
                for day, hours in allocations_by_day.items():
                    pending_allocations[(task.id, day)] = TaskDailyAllocation(task_id=task.id, work_date=day, allocated_hours=hours)
    db.add_all(pending_allocations.values())


def initialize_database():
    Base.metadata.create_all(bind=engine)
    columns = {column["name"] for column in inspect(engine).get_columns("projects")}
    with engine.begin() as connection:
        if "status" not in columns:
            connection.exec_driver_sql("ALTER TABLE projects ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'Draft'")
        if "archived" not in columns:
            connection.exec_driver_sql("ALTER TABLE projects ADD COLUMN archived BOOLEAN NOT NULL DEFAULT 0")
    db = SessionLocal()
    try:
        for project in db.query(Project).all():
            for snapshot in project.members or []:
                add_member_to_project(project, create_legacy_member(snapshot, db), db)
            legacy_tasks = (project.plan or {}).get("tasks", [])
            if legacy_tasks and not db.query(Task.id).filter(Task.project_id == project.id).first():
                id_map = {str(item.get("id")): f"P{project.id}-{item.get('id')}" for item in legacy_tasks}
                for order, item in enumerate(legacy_tasks):
                    db.add(Task(
                        id=id_map[str(item.get("id"))], project_id=project.id, task_order=order,
                        title=item.get("title", "Legacy task"), description=item.get("description", ""),
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
                    if assignee_id and db.get(TeamMember, str(assignee_id)):
                        member = db.get(TeamMember, str(assignee_id))
                        add_member_to_project(project, member, db)
                        db.add(TaskAssignment(task_id=task_id, member_id=member.id, assigned_hours=float(item.get("effort_hours", 1))))
                    for dependency in item.get("dependencies", []):
                        if str(dependency) in id_map:
                            db.add(TaskDependency(task_id=task_id, depends_on_task_id=id_map[str(dependency)]))
            if legacy_tasks and project.status == "Draft":
                statuses = {item.get("status", "Pending") for item in legacy_tasks}
                project.status = "Completed" if statuses == {"Completed"} else "Active"
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
    member = TeamMember(id=payload.id or str(uuid4()), **data)
    db.add(member)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "A team member with this ID already exists.") from error
    db.refresh(member)
    return member_dict(member)


@app.patch("/api/team-members/{member_id}")
def update_team_member(member_id: str, payload: MemberUpdate, db: Session = Depends(get_db)):
    member = db.get(TeamMember, member_id)
    if not member:
        raise HTTPException(404, "Team member not found.")
    changes = payload.model_dump(exclude_unset=True)
    available_from = changes.get("available_from", member.available_from)
    available_until = changes.get("available_until", member.available_until)
    if available_from and available_until and available_until < available_from:
        raise HTTPException(422, "Availability end date must be on or after the start date.")
    for field, value in changes.items():
        setattr(member, field, value)
    project_ids = [row.project_id for row in db.query(ProjectMember).filter(ProjectMember.member_id == member_id).all()]
    try:
        for project_id in project_ids:
            reschedule_project(db.get(Project, project_id), db)
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
    member_ids = set(payload.member_ids)
    for item in payload.members:
        member_id = item.id or str(uuid4())
        member = db.get(TeamMember, member_id) or create_legacy_member({**item.model_dump(), "id": member_id}, db)
        add_member_to_project(project, member, db)
        member_ids.add(member.id)
    db.flush()
    missing = [member_id for member_id in member_ids if not db.get(TeamMember, member_id)]
    if missing:
        db.rollback()
        raise HTTPException(422, f"Unknown team member IDs: {', '.join(missing)}.")
    for member_id in member_ids:
        add_member_to_project(project, db.get(TeamMember, member_id), db)
    try:
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(500, "The project could not be saved.") from error
    db.refresh(project)
    return project_dict(project, db)


@app.get("/api/projects")
def list_projects(archived: bool | None = None, db: Session = Depends(get_db)):
    query = db.query(Project)
    if archived is None:
        query = query.filter(Project.archived.is_(False), Project.status != "Draft", Project.plan.is_not(None))
    else:
        query = query.filter(Project.archived.is_(archived), Project.status != "Draft", Project.plan.is_not(None))
    projects = query.order_by(Project.updated_at.desc(), Project.id.desc()).all()
    return [project_dict(project, db, include_plan=False) for project in unique_named_projects(projects)]


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
    changes = payload.model_dump(exclude_unset=True)
    deadline = changes.get("deadline", project.deadline)
    if deadline and deadline < project.start_date:
        raise HTTPException(422, "Target deadline must be on or after the project start date.")
    for field, value in changes.items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project_dict(project, db)


@app.delete("/api/projects/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    task_ids = db.query(Task.id).filter(Task.project_id == project_id)
    db.query(TaskDependency).filter(TaskDependency.task_id.in_(task_ids)).delete(synchronize_session=False)
    db.query(TaskAssignment).filter(TaskAssignment.task_id.in_(task_ids)).delete(synchronize_session=False)
    db.query(Task).filter(Task.project_id == project_id).delete(synchronize_session=False)
    db.query(ProjectMember).filter(ProjectMember.project_id == project_id).delete(synchronize_session=False)
    db.delete(project)
    db.commit()


@app.post("/api/projects/{project_id}/archive")
def archive_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    project.archived = True
    db.commit()
    return project_dict(project, db, include_plan=False)


@app.post("/api/projects/{project_id}/restore")
def restore_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    project.archived = False
    db.commit()
    return project_dict(project, db, include_plan=False)


async def parse_document_upload(file: UploadFile):
    filename = Path(file.filename or "upload").name
    if re.search(r"[\\/\x00]", filename):
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
    filename, content, text, stories = await parse_document_upload(file)
    project.document_name = filename[:255]
    project.document_text = text
    project.stories = stories
    project.plan = None
    project.status = "Draft"
    task_ids = db.query(Task.id).filter(Task.project_id == project_id)
    db.query(TaskDependency).filter(TaskDependency.task_id.in_(task_ids)).delete(synchronize_session=False)
    db.query(TaskAssignment).filter(TaskAssignment.task_id.in_(task_ids)).delete(synchronize_session=False)
    db.query(Task).filter(Task.project_id == project_id).delete(synchronize_session=False)
    db.commit()
    return {"filename": project.document_name, "bytes": len(content), "stories": stories, "preview": text[:4000]}


@app.get("/api/projects/{project_id}/stories")
def get_stories(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    return project.stories


@app.post("/api/projects/{project_id}/team-members")
def add_member(project_id: int, payload: MemberCreate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    member_id = payload.id or str(uuid4())
    member = db.get(TeamMember, member_id)
    if member is None:
        member = TeamMember(id=member_id, **payload.model_dump(exclude={"id"}))
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
    if not project.stories:
        raise HTTPException(422, "Upload a readable user story document before generating a plan.")
    members = [member_dict(member) for member in project_members(project_id, db)]
    if not members:
        raise HTTPException(422, "Add at least one team member before generating a plan.")
    project_data = {column.name: getattr(project, column.name) for column in Project.__table__.columns}
    generated = generate_plan({**project_data, "members": members}, project.stories)
    id_map = {task["id"]: f"P{project.id}-{task['id']}" for task in generated["tasks"]}
    saved_tasks = [Task(
        id=id_map[item["id"]], project_id=project.id, task_order=order, title=item["title"],
        description=item["description"], story_ids=item.get("story_ids", []), source_story=item.get("source_story"),
        category=normalize_category(item["category"]), phase=item.get("phase"), effort_hours=item["effort_hours"],
        remaining_hours=item["remaining_hours"], priority=item["priority"], required_skills=item.get("required_skills", []),
        acceptance_criteria=item.get("acceptance_criteria", []), start_date=item.get("start_date"), end_date=item.get("end_date"),
        status=item["status"], uncertain=item.get("uncertain", False), rationale=item.get("rationale"), warning=item.get("warning"),
    ) for order, item in enumerate(generated["tasks"])]
    try:
        db.query(TaskDependency).filter(TaskDependency.task_id.in_(db.query(Task.id).filter(Task.project_id == project.id))).delete(synchronize_session=False)
        db.query(TaskAssignment).filter(TaskAssignment.task_id.in_(db.query(Task.id).filter(Task.project_id == project.id))).delete(synchronize_session=False)
        db.query(Task).filter(Task.project_id == project.id).delete(synchronize_session=False)
        db.add_all(saved_tasks)
        db.flush()
        for item in generated["tasks"]:
            task_id = id_map[item["id"]]
            if item.get("assignee_id") and db.get(TeamMember, item["assignee_id"]):
                db.add(TaskAssignment(task_id=task_id, member_id=item["assignee_id"], assigned_hours=item["effort_hours"]))
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
        project.plan = generated
        project.status = "Active"
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(500, "The plan and its tasks could not be saved; no partial plan was retained.") from error
    db.refresh(project)
    return project_plan(project, db)


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
    members = [member_dict(member) for member in project_members(project.id, db)]
    assignment_by_task = {
        assignment.task_id: assignment.member_id
        for assignment in db.query(TaskAssignment).join(Task).filter(Task.project_id == project.id).all()
    }
    tasks = db.query(Task).filter(Task.project_id == project.id).order_by(Task.task_order).all()
    tasks_by_id = {task.id: task for task in tasks}
    for assignment in db.query(TaskAssignment).join(Task).filter(Task.project_id == project.id).all():
        assignment.assigned_hours = tasks_by_id[assignment.task_id].effort_hours
    task_inputs = []
    for task in tasks:
        dependencies = [row.depends_on_task_id for row in db.query(TaskDependency).filter(TaskDependency.task_id == task.id).all()]
        task_inputs.append({
            "id": task.id,
            "title": task.title,
            "assignee_id": assignment_by_task.get(task.id),
            "effort_hours": task.effort_hours,
            "dependencies": dependencies,
            "requested_start_date": task.start_date,
        })
    project_data = {column.name: getattr(project, column.name) for column in Project.__table__.columns}
    try:
        scheduled = reschedule_tasks(project_data, members, task_inputs)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error

    for task, item in zip(tasks, scheduled):
        task.start_date = item.get("start_date")
        task.end_date = item.get("end_date")
        task.warning = item.get("warning")
    task_ids = [task.id for task in tasks]
    if task_ids:
        db.query(TaskDailyAllocation).filter(TaskDailyAllocation.task_id.in_(task_ids)).delete(synchronize_session=False)
    for task, item in zip(tasks, scheduled):
        for allocation in item.get("daily_allocations", []):
            db.add(TaskDailyAllocation(task_id=task.id, work_date=allocation["date"], allocated_hours=allocation["hours"]))


@app.patch("/api/tasks/{task_id}")
def update_task(task_id: str, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found.")
    changes = payload.model_dump(exclude_unset=True)
    reschedule_needed = bool({"assignee_id", "effort_hours", "start_date"} & changes.keys())
    if changes.get("status") and changes["status"] not in {"Pending", "In Progress", "Completed", "Blocked"}:
        raise HTTPException(422, "Status must be Pending, In Progress, Completed, or Blocked.")
    if "assignee_id" in changes:
        member_id = changes.pop("assignee_id")
        if member_id and not db.get(ProjectMember, (task.project_id, member_id)):
            raise HTTPException(422, "Assignee must be a member of this project.")
        assignment = db.get(TaskAssignment, task.id)
        if member_id:
            if assignment:
                assignment.member_id = member_id
            else:
                db.add(TaskAssignment(task_id=task.id, member_id=member_id, assigned_hours=task.effort_hours))
        elif assignment:
            db.delete(assignment)
    for field, value in changes.items():
        setattr(task, field, value)
    task.manually_edited = True
    project = db.get(Project, task.project_id)
    try:
        if reschedule_needed:
            db.flush()
            reschedule_project(project, db)
        statuses = [item.status for item in db.query(Task).filter(Task.project_id == task.project_id).all()]
        project.status = "Completed" if statuses and all(value == "Completed" for value in statuses) else "Active"
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(500, "The task update and schedule could not be saved.") from error
    return task_dict(task, db)


@app.get("/api/projects/{project_id}/dashboard")
def dashboard(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    plan = project_plan(project, db)
    if not plan:
        raise HTTPException(404, "Generate a plan before viewing the dashboard.")
    return {"project": {"id": project.id, "name": project.name, "deadline": project.deadline}, **plan}


def unique_named_projects(projects, limit=5):
    unique = []
    seen_names = set()
    for project in projects:
        key = re.sub(r"\s+", " ", project.name).strip().casefold()
        if key in seen_names:
            continue
        seen_names.add(key)
        unique.append(project)
        if len(unique) == limit:
            break
    return unique


@app.get("/api/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    projects = db.query(Project).all()
    active_projects = [project for project in projects if not project.archived]
    tasks = [task for task in db.query(Task).all() if not db.get(Project, task.project_id).archived]
    members = db.query(TeamMember).order_by(TeamMember.name).all()
    task_statuses = ("Pending", "In Progress", "Completed", "Blocked")
    task_counts = {status: sum(task.status == status for task in tasks) for status in task_statuses}
    project_counts = {
        "Draft": sum(project.status == "Draft" for project in active_projects),
        "Active": sum(project.status == "Active" for project in active_projects),
        "Completed": sum(project.status == "Completed" for project in active_projects),
        "Archived": sum(project.archived for project in projects),
    }
    today = date.today().isoformat()
    overdue = sum(bool(task.end_date and task.end_date < today and task.status != "Completed") for task in tasks)
    recent = db.query(Project).filter(
        Project.archived.is_(False),
        Project.status != "Draft",
        Project.plan.is_not(None),
    ).order_by(Project.updated_at.desc(), Project.id.desc()).all()
    recent = unique_named_projects(recent)
    recent_projects = []
    for project in recent:
        plan = project_plan(project, db)
        recent_projects.append({
            "id": project.id,
            "name": project.name,
            "status": "Archived" if project.archived else project.status,
            "deadline": project.deadline,
            "project_type": project.project_type,
            "task_count": plan["summary"]["task_count"] if plan else 0,
            "progress_percent": plan["summary"]["progress_percent"] if plan else 0,
        })
    upcoming = db.query(Project).filter(
        Project.archived.is_(False),
        Project.plan.is_not(None),
        Project.deadline.is_not(None),
        Project.deadline >= today,
        Project.status != "Completed",
    ).order_by(Project.deadline, Project.updated_at.desc(), Project.id.desc()).all()
    upcoming = unique_named_projects(upcoming)
    team_workload = []
    for member in members:
        assigned = sum(row.assigned_hours for row in db.query(TaskAssignment).join(Task).join(Project).filter(TaskAssignment.member_id == member.id, Project.archived.is_(False)).all())
        team_workload.append({"id": member.id, "name": member.name, "hours": round(assigned, 1), "allocation": member.allocation})
    weekly = {}
    for task in tasks:
        if not task.start_date:
            continue
        try:
            start = date.fromisoformat(task.start_date)
        except ValueError:
            continue
        week_start = (start - timedelta(days=start.weekday())).isoformat()
        bucket = weekly.setdefault(week_start, {"week": week_start, "planned": 0.0, "completed": 0.0})
        bucket["planned"] += task.effort_hours
        if task.status == "Completed":
            bucket["completed"] += task.effort_hours
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
        "upcoming_deadlines": [{"id": project.id, "name": project.name, "deadline": project.deadline, "status": project.status} for project in upcoming],
    }


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
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="planforge-project-{project.id}.csv"'})
