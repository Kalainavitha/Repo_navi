from pydantic import BaseModel, Field, field_validator

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAY_LOOKUP = {name.lower(): index for index, name in enumerate(WEEKDAY_NAMES)}


def _normalize_working_days(value):
    if value is None:
        return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    if isinstance(value, str):
        value = [item.strip() for item in value.split(",") if item.strip()]
    if not isinstance(value, list):
        raise ValueError("Choose at least one valid working day.")
    normalized = []
    for day in value:
        if isinstance(day, int):
            index = day
        elif isinstance(day, str):
            key = day.strip().lower()
            if key.isdigit():
                index = int(key)
            else:
                index = WEEKDAY_LOOKUP.get(key)
        else:
            raise ValueError("Choose at least one valid working day.")
        
        if index is None or not 0 <= index <= 6:
            raise ValueError("Choose at least one valid working day (Monday through Sunday).")
        normalized.append(WEEKDAY_NAMES[index])
    unique = []
    seen = set()
    for weekday in normalized:
        if weekday not in seen:
            seen.add(weekday)
            unique.append(weekday)
    return sorted(unique, key=lambda name: WEEKDAY_NAMES.index(name))


class MemberInput(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=80)
    skills: list[str] = Field(default_factory=list)
    experience: float = Field(default=2, ge=0, le=60)
    hours_per_day: float = Field(default=8, gt=0, le=24)
    working_days: list[str] = Field(default_factory=lambda: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
    allocation: float = Field(default=100, gt=0, le=100)
    available_from: str | None = None
    available_until: str | None = None
    leave_dates: list[str] = Field(default_factory=list)
    email: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    hourly_rate: float | None = Field(default=None, ge=0)
    is_lead: bool = False
    additional_role: str | None = Field(default=None, max_length=80)

    @field_validator("working_days", mode="before")
    @classmethod
    def valid_member_working_days(cls, value):
        return _normalize_working_days(value)
        
    @field_validator("available_from", "available_until", "email", "notes", "additional_role", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        if v == "":
            return None
        return v


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=5000)
    project_type: str = "Web Application"
    start_date: str
    deadline: str | None = None
    priority: str = "Medium"
    complexity: str = "Medium"
    working_days: list[str] = Field(default_factory=lambda: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
    hours_per_day: float = Field(default=8, gt=0, le=24)
    holidays: list[str] = Field(default_factory=list)
    buffer_percent: int = Field(default=10, ge=0, le=100)
    members: list[MemberInput] = Field(default_factory=list)
    member_ids: list[str] = Field(default_factory=list)

    @field_validator("working_days", mode="before")
    @classmethod
    def valid_working_days(cls, value):
        return _normalize_working_days(value)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    status: str | None = None
    assignee_id: str | None = None
    effort_hours: float | None = Field(default=None, gt=0, le=10000)
    start_date: str | None = None
    end_date: str | None = None


class MemberCreate(MemberInput):
    pass


class MemberUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    role: str | None = Field(default=None, min_length=1, max_length=80)
    skills: list[str] | None = None
    experience: float | None = Field(default=None, ge=0, le=60)
    hours_per_day: float | None = Field(default=None, gt=0, le=24)
    working_days: list[str] | None = None
    allocation: float | None = Field(default=None, gt=0, le=100)
    available_from: str | None = None
    available_until: str | None = None
    leave_dates: list[str] | None = None
    email: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    hourly_rate: float | None = Field(default=None, ge=0)
    is_lead: bool | None = None
    additional_role: str | None = Field(default=None, max_length=80)

    @field_validator("working_days", mode="before")
    @classmethod
    def valid_member_working_days(cls, value):
        if value is None:
            return None
        return _normalize_working_days(value)

    @field_validator("available_from", "available_until", "email", "notes", "additional_role", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        if v == "":
            return None
        return v


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    deadline: str | None = None
    priority: str | None = None
    complexity: str | None = None
    holidays: list[str] | None = None
    buffer_percent: int | None = Field(default=None, ge=0, le=100)