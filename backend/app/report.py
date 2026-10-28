"""Weekly status report: a ready-to-send summary built from the plan, with no AI involved."""
from datetime import date, timedelta

SEVERITY_RANK = {"High": 0, "Medium": 1, "Low": 2}


def week_bounds(any_day: date) -> tuple[date, date]:
    start = any_day - timedelta(days=any_day.weekday())
    return start, start + timedelta(days=6)


def _day(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _nice(day: date | None) -> str:
    return f"{day.strftime('%a')} {day.day} {day.strftime('%b')}" if day else "-"


def _hours(value: float) -> str:
    return f"{value:g}h"


def _task_line(task: dict) -> dict:
    return {
        "id": task["id"], "title": task["title"], "assignee_name": task.get("assignee_name"),
        "end_date": task.get("end_date"), "status": task["status"], "priority": task.get("priority"),
    }


def build_report(project: dict, tasks: list[dict], summary: dict, any_day: date, today: date) -> dict:
    week_start, week_end = week_bounds(any_day)
    next_start, next_end = week_start + timedelta(days=7), week_end + timedelta(days=7)
    reference = min(today, week_end)  # for a past week, "late" means late as of that week's end

    total = len(tasks)
    done = [t for t in tasks if t["status"] == "Completed"]
    effort_total = round(sum(float(t.get("effort_hours") or 0) for t in tasks), 1)
    effort_done = round(sum(float(t.get("effort_hours") or 0) for t in done), 1)

    def completed_in_week(task: dict) -> bool:
        finished = _day(task.get("completed_at")) or _day(task.get("end_date"))
        return task["status"] == "Completed" and finished is not None and week_start <= finished <= week_end

    completed_week = [t for t in tasks if completed_in_week(t)]
    in_progress = [t for t in tasks if t["status"] == "In Progress"]
    blocked = [t for t in tasks if t["status"] == "Blocked"]
    overdue = [t for t in tasks if t["status"] != "Completed" and (_day(t.get("end_date")) or date.max) < reference]

    # next week: hours per person from the daily allocations
    by_person: dict[str, dict] = {}
    for task in tasks:
        if task["status"] == "Completed":
            continue
        for allocation in task.get("daily_allocations", []):
            day = _day(allocation.get("date"))
            if day and next_start <= day <= next_end:
                person = by_person.setdefault(task.get("assignee_name") or "Unassigned", {"name": task.get("assignee_name") or "Unassigned", "hours": 0.0, "tasks": []})
                person["hours"] = round(person["hours"] + float(allocation.get("hours") or 0), 2)
                if task["title"] not in person["tasks"]:
                    person["tasks"].append(task["title"])
    next_week = sorted(by_person.values(), key=lambda item: -item["hours"])

    risks = sorted(
        [r for r in summary.get("risks", []) if isinstance(r, dict) and r.get("message")],
        key=lambda r: SEVERITY_RANK.get(r.get("severity"), 3),
    )[:3]

    probability = summary.get("on_time_probability")
    deadline = _day(project.get("deadline"))
    reasons = []
    status = "On track"
    if overdue:
        status = "At risk"
        reasons.append(f"{len(overdue)} task(s) are past their planned end date")
    if blocked:
        status = "At risk"
        reasons.append(f"{len(blocked)} task(s) are halted")
    if probability is not None and probability < 0.7:
        status = "At risk"
        reasons.append(f"only a {round(probability * 100)}% chance of finishing by the deadline")
    if (deadline and reference > deadline and len(done) < total) or (probability is not None and probability < 0.4) or summary.get("deadline_feasible") is False:
        status = "Late"
        if deadline and reference > deadline and len(done) < total:
            reasons.append("the deadline has passed with work still open")
        elif summary.get("deadline_feasible") is False:
            reasons.append("the current schedule finishes after the deadline")
    if not reasons:
        reasons.append("no overdue or halted work and the forecast is healthy" if probability is not None else "no overdue or halted work")

    forecast_line = None
    if probability is not None and deadline:
        forecast_line = (
            f"{round(probability * 100)}% chance of finishing by {_nice(deadline)}"
            + (f"; most likely {_nice(_day(summary.get('forecast_p50')))}, safe date {_nice(_day(summary.get('forecast_p85')))}" if summary.get("forecast_p50") else "")
            + "."
        )

    report = {
        "project": project.get("name"),
        "week_start": week_start.isoformat(), "week_end": week_end.isoformat(),
        "week_label": f"{_nice(week_start)} - {_nice(week_end)} {week_end.year}",
        "status": status, "status_reasons": reasons,
        "progress": {"done": len(done), "total": total, "percent": round(100 * len(done) / total) if total else 0,
                     "hours_done": effort_done, "hours_total": effort_total, "hours_remaining": round(effort_total - effort_done, 1)},
        "completed_this_week": [_task_line(t) for t in completed_week],
        "in_progress": [_task_line(t) for t in in_progress],
        "blocked": [_task_line(t) for t in blocked],
        "overdue": [_task_line(t) for t in overdue],
        "next_week": next_week,
        "next_week_label": f"{_nice(next_start)} - {_nice(next_end)}",
        "risks": [{"severity": r.get("severity"), "message": r["message"]} for r in risks],
        "forecast": forecast_line,
        "deadline": deadline.isoformat() if deadline else None,
    }
    report["markdown"] = to_markdown(report)
    return report


def to_markdown(report: dict) -> str:
    def lines(items, fmt, empty):
        return [fmt(item) for item in items] or [f"- {empty}"]

    who = lambda t: f" ({t['assignee_name']})" if t.get("assignee_name") else ""
    due = lambda t: f", due {_nice(_day(t.get('end_date')))}" if t.get("end_date") else ""
    progress = report["progress"]
    out = [
        f"# Weekly status: {report['project']}",
        f"**Week:** {report['week_label']}",
        f"**Overall:** {report['status']} ({'; '.join(report['status_reasons'])})",
        f"**Progress:** {progress['done']}/{progress['total']} tasks done ({progress['percent']}%), "
        f"{_hours(progress['hours_done'])} of {_hours(progress['hours_total'])}, {_hours(progress['hours_remaining'])} remaining",
    ]
    if report["forecast"]:
        out.append(f"**Forecast:** {report['forecast']}")
    out += ["", "## Completed this week"] + lines(report["completed_this_week"], lambda t: f"- {t['title']}{who(t)}", "Nothing completed this week.")
    out += ["", "## In progress"] + lines(report["in_progress"], lambda t: f"- {t['title']}{who(t)}{due(t)}", "Nothing in progress.")
    out += ["", "## Blocked or overdue"]
    attention = report["blocked"] + [t for t in report["overdue"] if t["id"] not in {b["id"] for b in report["blocked"]}]
    out += lines(attention, lambda t: f"- {'HALTED' if t['status'] == 'Blocked' else 'OVERDUE'}: {t['title']}{who(t)}{due(t)}", "None.")
    out += ["", f"## Next week ({report['next_week_label']})"]
    out += lines(report["next_week"], lambda p: f"- {p['name']}: {_hours(p['hours'])} - " + "; ".join(p["tasks"][:3]) + (" ..." if len(p["tasks"]) > 3 else ""), "No work is scheduled.")
    out += ["", "## Top risks"] + lines(report["risks"], lambda r: f"- [{r['severity']}] {r['message']}", "No significant risks.")
    return "\n".join(out) + "\n"
