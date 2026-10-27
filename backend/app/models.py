from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    project_type: Mapped[str] = mapped_column(String(80), default="Web Application")
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    deadline: Mapped[str | None] = mapped_column(String(10), nullable=True)
    priority: Mapped[str] = mapped_column(String(16), default="Medium")
    complexity: Mapped[str] = mapped_column(String(16), default="Medium")
    working_days: Mapped[list] = mapped_column(JSON, default=lambda: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
    hours_per_day: Mapped[float] = mapped_column(default=8.0)
    holidays: Mapped[list] = mapped_column(JSON, default=list)
    buffer_percent: Mapped[int] = mapped_column(Integer, default=10)
    members: Mapped[list] = mapped_column(JSON, default=list)
    stories: Mapped[list] = mapped_column(JSON, default=list)
    plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    document_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="Draft", nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class TeamMember(Base):
    __tablename__ = "team_members"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(80), nullable=False)
    skills: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    experience: Mapped[float] = mapped_column(Float, default=2, nullable=False)
    hours_per_day: Mapped[float] = mapped_column(Float, default=8, nullable=False)
    working_days: Mapped[list] = mapped_column(JSON, default=lambda: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], nullable=False)
    allocation: Mapped[float] = mapped_column(Float, default=100, nullable=False)
    available_from: Mapped[str | None] = mapped_column(String(10), nullable=True)
    available_until: Mapped[str | None] = mapped_column(String(10), nullable=True)
    leave_dates: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    hourly_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ProjectMember(Base):
    __tablename__ = "project_members"

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    member_id: Mapped[str] = mapped_column(ForeignKey("team_members.id", ondelete="RESTRICT"), primary_key=True)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    task_order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    story_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    source_story: Mapped[str | None] = mapped_column(String(240), nullable=True)
    category: Mapped[str] = mapped_column(String(80), default="Implementation", nullable=False)
    phase: Mapped[str | None] = mapped_column(String(80), nullable=True)
    effort_hours: Mapped[float] = mapped_column(Float, nullable=False)
    remaining_hours: Mapped[float] = mapped_column(Float, nullable=False)
    priority: Mapped[str] = mapped_column(String(16), default="Medium", nullable=False)
    required_skills: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    acceptance_criteria: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    start_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="Pending", nullable=False)
    uncertain: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    manually_edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class TaskAssignment(Base):
    __tablename__ = "task_assignments"

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    member_id: Mapped[str] = mapped_column(ForeignKey("team_members.id", ondelete="RESTRICT"), nullable=False, index=True)
    assigned_hours: Mapped[float] = mapped_column(Float, nullable=False)


class TaskDailyAllocation(Base):
    __tablename__ = "task_daily_allocations"

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    work_date: Mapped[str] = mapped_column(String(10), primary_key=True)
    allocated_hours: Mapped[float] = mapped_column(Float, nullable=False)


class TaskDependency(Base):
    __tablename__ = "task_dependencies"

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    depends_on_task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
