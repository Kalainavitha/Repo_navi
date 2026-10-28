from datetime import datetime
from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from .database import Base

class TeamMember(Base):
    __tablename__ = "team_members"
    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    role = Column(String(128), nullable=False, default="Team Member")
    skills = Column(JSON, default=list)
    experience = Column(Float, default=0)
    hours_per_day = Column(Float, default=8)
    working_days = Column(JSON, default=list)
    allocation = Column(Float, default=100)
    available_from = Column(String(32), nullable=True)
    available_until = Column(String(32), nullable=True)
    leave_dates = Column(JSON, default=list)
    email = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    hourly_rate = Column(Float, nullable=True)
    is_lead = Column(Boolean, default=False, nullable=False, server_default="0")
    additional_role = Column(String(128), nullable=True)

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    project_type = Column(String(128), default="Other")
    start_date = Column(String(32), nullable=False)
    deadline = Column(String(32), nullable=True)
    priority = Column(String(32), default="Medium")
    complexity = Column(String(32), default="Medium")
    working_days = Column(JSON, default=list)
    hours_per_day = Column(Float, default=8)
    holidays = Column(JSON, default=list)
    buffer_percent = Column(Float, default=10)
    document_name = Column(String(255), nullable=True)
    document_text = Column(Text, nullable=True)
    stories = Column(JSON, default=list)
    plan = Column(JSON, nullable=True)
    members = Column(JSON, default=list) # Legacy snapshot
    status = Column(String(16), default="Draft")
    archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ProjectMember(Base):
    __tablename__ = "project_members"
    project_id = Column(Integer, ForeignKey("projects.id"), primary_key=True)
    member_id = Column(String(64), ForeignKey("team_members.id"), primary_key=True)

class Task(Base):
    __tablename__ = "tasks"
    id = Column(String(64), primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    task_order = Column(Integer, default=0)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    # Added summary column to hold the short UI text
    summary = Column(Text, default="") 
    story_ids = Column(JSON, default=list)
    source_story = Column(String(255), nullable=True)
    category = Column(String(64), default="Other")
    phase = Column(String(64), nullable=True)
    effort_hours = Column(Float, default=1)
    remaining_hours = Column(Float, default=1)
    priority = Column(String(32), default="Medium")
    required_skills = Column(JSON, default=list)
    acceptance_criteria = Column(JSON, default=list)
    start_date = Column(String(32), nullable=True)
    end_date = Column(String(32), nullable=True)
    status = Column(String(32), default="Pending")
    uncertain = Column(Boolean, default=False)
    rationale = Column(Text, nullable=True)
    warning = Column(Text, nullable=True)
    manually_edited = Column(Boolean, default=False)
    risk_level = Column(String(16), default="Low")
    risk_note = Column(Text, nullable=True)
    started_at = Column(String(32), nullable=True)
    completed_at = Column(String(32), nullable=True)

class TaskAssignment(Base):
    __tablename__ = "task_assignments"
    task_id = Column(String(64), ForeignKey("tasks.id"), primary_key=True)
    member_id = Column(String(64), ForeignKey("team_members.id"), nullable=False)
    assigned_hours = Column(Float, default=0)

class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    task_id = Column(String(64), ForeignKey("tasks.id"), primary_key=True)
    depends_on_task_id = Column(String(64), ForeignKey("tasks.id"), primary_key=True)

class TaskDailyAllocation(Base):
    __tablename__ = "task_daily_allocations"
    task_id = Column(String(64), ForeignKey("tasks.id"), primary_key=True)
    work_date = Column(String(32), primary_key=True)
    allocated_hours = Column(Float, default=0)