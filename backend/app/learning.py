"""Estimate Coach: learn how long people really take compared with the plan.

For every completed task that has a start and a finish timestamp we compare the working days it actually took
(In process -> Completed) with the working days it was planned for. A person's average ratio, per phase, is then
used to stretch or trim new estimates. Few samples are shrunk towards "no change" and outliers are clamped, so a
single odd task cannot swing the plan.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from .models import Project, Task, TaskAssignment, TeamMember
from .planning import _normalize_workdays

MIN_SAMPLES = 3          # tasks needed before a person/phase is trusted
SHRINK = 3.0             # n / (n + SHRINK) of the observed gap is applied
CLAMP = (0.5, 2.5)       # a single task cannot count for more than this
MAX_AGE_DAYS = 180       # older history is ignored
IGNORE_BELOW = 0.05      # factors within 5% of 1.0 are treated as "accurate"


def _working_days(start: date, end: date, workdays: set[int]) -> int:
    if end < start:
        start, end = end, start
    count = 0
    cursor = start
    while cursor <= end:
        if cursor.weekday() in workdays:
            count += 1
        cursor += timedelta(days=1)
    return max(1, count)


def _day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def observations(db: Session, today: date | None = None) -> list[dict]:
    today = today or date.today()
    rows = db.query(Task, TaskAssignment.member_id, Project).join(
        TaskAssignment, TaskAssignment.task_id == Task.id,
    ).join(Project, Project.id == Task.project_id).filter(
        Task.status == "Completed", Task.started_at.is_not(None), Task.completed_at.is_not(None),
        Task.start_date.is_not(None), Task.end_date.is_not(None),
    ).all()
    found = []
    for task, member_id, project in rows:
        started, finished = _day(task.started_at), _day(task.completed_at)
        planned_start, planned_end = _day(task.start_date), _day(task.end_date)
        if not (started and finished and planned_start and planned_end):
            continue
        if (today - finished).days > MAX_AGE_DAYS:
            continue
        workdays = _normalize_workdays(project.working_days)
        planned = _working_days(planned_start, planned_end, workdays)
        actual = _working_days(started, finished, workdays)
        ratio = min(CLAMP[1], max(CLAMP[0], actual / planned))
        found.append({"member_id": member_id, "phase": task.phase or task.category or "Other", "ratio": ratio})
    return found


def _factor(ratios: list[float]) -> float | None:
    if len(ratios) < MIN_SAMPLES:
        return None
    mean = sum(ratios) / len(ratios)
    return 1.0 + (mean - 1.0) * len(ratios) / (len(ratios) + SHRINK)


class Calibration:
    """Callable `(member_id, phase) -> factor` (1.0 = no change). Most specific evidence wins."""

    def __init__(self, found: list[dict]):
        by_pair, by_member, by_phase = defaultdict(list), defaultdict(list), defaultdict(list)
        for item in found:
            by_pair[(item["member_id"], item["phase"])].append(item["ratio"])
            by_member[item["member_id"]].append(item["ratio"])
            by_phase[item["phase"]].append(item["ratio"])
        self.pair = {key: _factor(values) for key, values in by_pair.items()}
        self.member = {key: _factor(values) for key, values in by_member.items()}
        self.phase = {key: _factor(values) for key, values in by_phase.items()}
        self.samples = len(found)

    def __call__(self, member_id: str, phase: str) -> float:
        for table, key in ((self.pair, (member_id, phase)), (self.member, member_id), (self.phase, phase)):
            value = table.get(key)
            if value is not None:
                return 1.0 if abs(value - 1.0) < IGNORE_BELOW else round(value, 2)
        return 1.0


def build_calibration(db: Session, today: date | None = None) -> Calibration:
    return Calibration(observations(db, today))


def _label(samples: int, ratio: float | None, strongest: tuple[str, float] | None) -> str:
    if samples < MIN_SAMPLES:
        return f"Learning: {samples} of {MIN_SAMPLES} completed tasks needed before estimates are adjusted."
    if ratio is None or abs(ratio - 1.0) < IGNORE_BELOW:
        return "Estimates for this person have been accurate."
    percent = round(abs(ratio - 1.0) * 100)
    text = f"Tends to take {percent}% longer than planned" if ratio > 1 else f"Tends to finish {percent}% faster than planned"
    if strongest and abs(strongest[1] - 1.0) >= 0.15 and (strongest[1] > 1) == (ratio > 1):
        text += f", most on {strongest[0]}"
    return text + "."


def accuracy_report(db: Session, today: date | None = None) -> dict:
    found = observations(db, today)
    calibration = Calibration(found)
    per_member = defaultdict(list)
    per_pair = defaultdict(list)
    for item in found:
        per_member[item["member_id"]].append(item["ratio"])
        per_pair[(item["member_id"], item["phase"])].append(item["ratio"])
    people = []
    for member in db.query(TeamMember).order_by(TeamMember.name).all():
        ratios = per_member.get(member.id, [])
        phases = [
            {"phase": phase, "samples": len(values), "ratio": round(sum(values) / len(values), 2), "applied_factor": calibration(member.id, phase)}
            for (member_id, phase), values in sorted(per_pair.items()) if member_id == member.id
        ]
        average = round(sum(ratios) / len(ratios), 2) if ratios else None
        applied = _factor(ratios)
        strongest = max(((p["phase"], p["ratio"]) for p in phases if p["samples"] >= 2), key=lambda pair: abs(pair[1] - 1.0), default=None)
        people.append({
            "id": member.id, "name": member.name, "role": member.role, "samples": len(ratios),
            "avg_ratio": average, "applied_factor": round(applied, 2) if applied is not None else None,
            "learned": len(ratios) >= MIN_SAMPLES, "by_phase": phases, "label": _label(len(ratios), applied, strongest),
        })
    return {"samples": len(found), "min_samples": MIN_SAMPLES, "members": people}
