"""On-time forecast (Monte Carlo over the remaining work)."""
import time
from datetime import date

from app.document_processing import extract_stories
from app.forecast import attach_to_summary, forecast_plan
from app.planning import generate_plan

from tests.test_plan_audit import PORTAL, project, team

START = date(2026, 11, 2)


def planned(deadline="2026-12-18", members=None):
    proj = project(deadline=deadline, members=members)
    plan = generate_plan(proj, extract_stories(PORTAL))
    return proj, plan


def forecast_of(proj, plan, runs=200, seed=1, today=START):
    return forecast_plan(proj, proj["members"], plan["tasks"], today, None, runs=runs, seed=seed)


def test_forecast_is_deterministic_and_ordered():
    proj, plan = planned()
    first = forecast_of(proj, plan)
    second = forecast_of(proj, plan)
    assert first == second
    assert first["earliest"] <= first["p50"] <= first["p85"] <= first["p95"] <= first["latest"]
    assert sum(bucket["count"] for bucket in first["histogram"]) == first["runs"] == 200
    assert 0.0 <= first["probability_on_time"] <= 1.0
    assert first["confidence"] in {"High", "Medium", "Low"}
    assert first["critical_tasks"] and all(0 < item["share"] <= 1 for item in first["critical_tasks"])
    assert forecast_of(proj, plan, seed=2)["runs"] == 200  # a different seed still works


def test_odds_fall_as_the_deadline_gets_tighter_and_rise_with_a_bigger_team():
    proj, plan = planned()
    finish = forecast_of(proj, plan)["p50"]
    loose = dict(proj, deadline="2026-12-31")
    tight = dict(proj, deadline=finish)  # the median finish date: roughly a coin flip
    impossible = dict(proj, deadline="2026-11-03")
    odds_loose = forecast_of(loose, plan)["probability_on_time"]
    odds_tight = forecast_of(tight, plan)["probability_on_time"]
    odds_impossible = forecast_of(impossible, plan)["probability_on_time"]
    assert odds_loose >= odds_tight >= odds_impossible
    assert odds_loose > 0.9
    assert 0.3 <= odds_tight <= 0.95
    assert odds_impossible < 0.05

    # a smaller team (planned with fewer people) is slower and therefore less likely to make a tight date
    small_proj, small_plan = planned(members=[m for m in team() if m["id"] in {"PM", "BE1", "FE1", "QA"}])
    assert forecast_of(small_proj, small_plan)["p50"] >= forecast_of(proj, plan)["p50"]


def test_complexity_widens_the_spread():
    proj, plan = planned()
    easy = forecast_of(dict(proj, complexity="Low"), plan)
    hard = forecast_of(dict(proj, complexity="High"), plan)
    assert hard["p95"] >= easy["p95"]


def test_finished_or_deadline_less_plans_are_handled():
    proj, plan = planned()
    done = [dict(task, status="Completed") for task in plan["tasks"]]
    result = forecast_plan(proj, proj["members"], done, date(2027, 1, 4), None)
    assert result["runs"] == 0 and result["probability_on_time"] == 1.0

    no_deadline = forecast_of(dict(proj, deadline=None), plan)
    assert no_deadline["probability_on_time"] is None and no_deadline["p50"]


def test_forecast_only_looks_at_unfinished_work():
    proj, plan = planned()
    today = date(2026, 11, 20)
    mostly_done = [dict(task, status="Completed") if index < len(plan["tasks"]) - 2 else dict(task) for index, task in enumerate(plan["tasks"])]
    result = forecast_plan(proj, proj["members"], mostly_done, today, None, runs=100, seed=3)
    assert result["remaining_tasks"] <= 2
    assert result["p50"] >= today.isoformat()


def test_a_poor_forecast_adds_a_risk_to_the_summary():
    summary = {"risks": [{"type": "skills", "severity": "Low", "message": "x"}], "risk_level": "Low"}
    attach_to_summary(summary, {"probability_on_time": 0.35, "p50": "2026-12-20", "p85": "2026-12-28"})
    assert summary["risk_level"] == "High"
    assert summary["risks"][0]["type"] == "forecast" and "35%" in summary["risks"][0]["message"]
    attach_to_summary(summary, {"probability_on_time": 0.95, "p50": "2026-12-01", "p85": "2026-12-03"})
    assert all(risk["type"] != "forecast" for risk in summary["risks"])  # replaced, not stacked


def test_forecast_is_fast_enough_for_a_big_plan():
    topics = [f"As a user, I want feature number {i} with reports and an api so that I can work." for i in range(20)]
    proj = project(deadline="2027-03-01")
    plan = generate_plan(proj, extract_stories("\n".join(topics)))
    started = time.perf_counter()
    forecast_of(proj, plan, runs=300)
    assert time.perf_counter() - started < 15


def test_endpoint_and_stored_summary(client):
    from tests.test_replan import make_member, make_plan

    members = [make_member(client, name="Ana"), make_member(client, name="Bo", experience=3)]
    project_id, plan = make_plan(client, members)
    assert "on_time_probability" in plan["summary"] and plan["summary"]["on_time_probability"] is not None

    live = client.get(f"/api/projects/{project_id}/forecast", params={"today": "2026-11-02", "runs": 100})
    assert live.status_code == 200, live.text
    body = live.json()
    assert body["runs"] == 100 and body["deadline"] == "2026-12-18"
    assert body["p50"] <= body["p85"] <= body["p95"]
    assert client.get(f"/api/projects/{project_id}/forecast", params={"today": "bad"}).status_code == 422
    assert client.get("/api/projects/9999/forecast").status_code == 404
