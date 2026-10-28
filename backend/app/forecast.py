"""On-time forecast: re-run the remaining work many times with random estimate overruns.

Each run multiplies the unfinished tasks' hours by a random factor (a triangular distribution that is wider for
complex projects and for tasks flagged uncertain or high-risk), reschedules them around the same calendars the
real plan uses, and records the finish date. The spread of finish dates gives the chance of meeting the deadline.
It is seeded, so the same plan always gives the same answer.
"""
import random
from collections import Counter
from datetime import date

from .planning import _normalize_date, replan_from

# (lowest factor, most likely factor, worst factor) by project complexity
SPREAD = {"Low": (0.9, 1.0, 1.4), "Medium": (0.9, 1.05, 1.6), "High": (0.9, 1.15, 1.9)}
DEFAULT_RUNS = 300


def _percentile(sorted_dates: list[date], share: float) -> date:
    return sorted_dates[min(len(sorted_dates) - 1, max(0, round(share * (len(sorted_dates) - 1))))]


def _critical_chain(results: list[dict]) -> list[str]:
    """The last task to finish plus, repeatedly, the dependency that finished latest: what set the finish date."""
    by_id = {item["id"]: item for item in results}
    ends = {item["id"]: _normalize_date(item.get("end_date")) for item in results}
    open_ids = [task_id for task_id, end in ends.items() if end]
    if not open_ids:
        return []
    current = max(open_ids, key=lambda task_id: ends[task_id])
    chain = [current]
    while True:
        dependencies = [dep for dep in by_id[current].get("dependencies", []) if dep in ends and ends[dep]]
        if not dependencies:
            return chain
        current = max(dependencies, key=lambda dep: ends[dep])
        if current in chain:
            return chain
        chain.append(current)


def forecast_plan(project: dict, members: list[dict], tasks: list[dict], today: date, existing_bookings: dict | None = None,
                  runs: int = DEFAULT_RUNS, seed: int = 0) -> dict:
    deadline = _normalize_date(project.get("deadline"))
    complexity = str(project.get("complexity") or "Medium").title()
    low, likely, high = SPREAD.get(complexity, SPREAD["Medium"])
    open_tasks = [t for t in tasks if t.get("status") != "Completed" and t.get("assignee_id")]

    if not open_tasks:
        ends = [_normalize_date(t.get("end_date")) for t in tasks if t.get("end_date")]
        finish = max(ends) if ends else None
        return {
            "runs": 0, "remaining_tasks": 0, "probability_on_time": (1.0 if (deadline and finish and finish <= deadline) else None),
            "p50": finish.isoformat() if finish else None, "p85": finish.isoformat() if finish else None, "p95": finish.isoformat() if finish else None,
            "earliest": finish.isoformat() if finish else None, "latest": finish.isoformat() if finish else None,
            "histogram": [], "critical_tasks": [], "confidence": "High", "deadline": deadline.isoformat() if deadline else None,
        }

    rng = random.Random(seed)
    finishes: list[date] = []
    critical = Counter()
    title_of = {t["id"]: t["title"] for t in tasks}
    for _ in range(runs):
        trial = []
        for task in tasks:
            if task.get("status") == "Completed" or not task.get("assignee_id"):
                trial.append(dict(task))
                continue
            top = high + (0.3 if (task.get("uncertain") or task.get("risk_level") == "High") else 0.0)
            factor = rng.triangular(low, top, likely)
            base = float(task.get("remaining_hours") or 0) or float(task.get("effort_hours") or 0)
            trial.append({**task, "remaining_hours": round(base * factor, 2)})
        results = replan_from(project, members, trial, today, existing_bookings)
        ends = [_normalize_date(item.get("end_date")) for item in results if item.get("end_date")]
        finishes.append(max(ends))
        for task_id in _critical_chain(results):
            critical[task_id] += 1

    finishes.sort()
    p50, p85, p95 = _percentile(finishes, 0.5), _percentile(finishes, 0.85), _percentile(finishes, 0.95)
    on_time = (sum(1 for day in finishes if day <= deadline) / len(finishes)) if deadline else None
    spread = (p95 - p50).days
    counts = Counter(finishes)
    return {
        "runs": runs,
        "remaining_tasks": len(open_tasks),
        "probability_on_time": round(on_time, 3) if on_time is not None else None,
        "p50": p50.isoformat(), "p85": p85.isoformat(), "p95": p95.isoformat(),
        "earliest": finishes[0].isoformat(), "latest": finishes[-1].isoformat(),
        "histogram": [{"date": day.isoformat(), "count": counts[day]} for day in sorted(counts)],
        "critical_tasks": [
            {"id": task_id, "title": title_of.get(task_id, task_id), "share": round(count / runs, 3)}
            for task_id, count in critical.most_common(5)
        ],
        "confidence": "High" if spread <= 3 else "Medium" if spread <= 8 else "Low",
        "deadline": deadline.isoformat() if deadline else None,
    }


def attach_to_summary(summary: dict, forecast: dict) -> dict:
    """Store the headline numbers on the plan summary and raise a risk when the odds are poor."""
    summary["on_time_probability"] = forecast.get("probability_on_time")
    summary["forecast_p50"] = forecast.get("p50")
    summary["forecast_p85"] = forecast.get("p85")
    probability = forecast.get("probability_on_time")
    risks = [risk for risk in summary.get("risks", []) if not (isinstance(risk, dict) and risk.get("type") == "forecast")]
    if probability is not None and probability < 0.7:
        severity = "High" if probability < 0.4 else "Medium"
        risks.append({
            "type": "forecast", "severity": severity,
            "message": f"Only a {round(probability * 100)}% chance of finishing by the deadline; a safe finish date is {forecast.get('p85')}.",
            "task_id": None, "member_id": None,
        })
        if severity == "High" or summary.get("risk_level") == "Low":
            summary["risk_level"] = severity
        risks.sort(key=lambda risk: {"High": 0, "Medium": 1, "Low": 2}.get(risk.get("severity"), 3) if isinstance(risk, dict) else 3)
    summary["risks"] = risks
    return summary
