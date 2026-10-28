"""Weekly status report."""
from datetime import date

from app.report import build_report, week_bounds
from tests.test_replan import make_member, make_plan

PROJECT = {"name": "Billing", "deadline": "2026-12-18"}
TODAY = date(2026, 11, 12)  # a Thursday; its week is Mon 9 Nov - Sun 15 Nov


def task(id_, status="Pending", end="2026-11-20", who="Ana", **extra):
    return {"id": id_, "title": f"Task {id_}", "status": status, "assignee_name": who, "end_date": end,
            "effort_hours": 8, "priority": "High", "daily_allocations": [], **extra}


def test_weeks_start_on_monday():
    assert week_bounds(date(2026, 11, 12)) == (date(2026, 11, 9), date(2026, 11, 15))
    assert week_bounds(date(2026, 11, 9)) == (date(2026, 11, 9), date(2026, 11, 15))
    assert week_bounds(date(2026, 11, 15)) == (date(2026, 11, 9), date(2026, 11, 15))


def test_sections_pick_the_right_tasks_for_the_week():
    tasks = [
        task("a", "Completed", completed_at="2026-11-10T16:00:00"),            # this week
        task("b", "Completed", completed_at="2026-11-04T16:00:00"),            # last week
        task("c", "Completed", end="2026-11-11"),                              # no timestamp: falls back to the planned end
        task("d", "In Progress"),
        task("e", "Blocked"),
        task("f", "Pending", end="2026-11-06"),                                # overdue
        task("g", "Pending", daily_allocations=[{"date": "2026-11-16", "hours": 6}, {"date": "2026-11-17", "hours": 4}]),
        task("h", "Pending", who="Bo", daily_allocations=[{"date": "2026-11-18", "hours": 3}, {"date": "2026-11-23", "hours": 8}]),
    ]
    report = build_report(PROJECT, tasks, {}, TODAY, TODAY)
    assert [t["id"] for t in report["completed_this_week"]] == ["a", "c"]
    assert [t["id"] for t in report["in_progress"]] == ["d"]
    assert [t["id"] for t in report["blocked"]] == ["e"]
    assert [t["id"] for t in report["overdue"]] == ["f"]
    assert [(p["name"], p["hours"]) for p in report["next_week"]] == [("Ana", 10.0), ("Bo", 3.0)]  # 23 Nov is the week after next
    assert report["progress"] == {"done": 3, "total": 8, "percent": 38, "hours_done": 24.0, "hours_total": 64.0, "hours_remaining": 40.0}
    assert report["week_label"].startswith("Mon 9 Nov") and report["week_label"].endswith("Sun 15 Nov 2026")


def test_overall_status_levels():
    healthy = build_report(PROJECT, [task("a", "In Progress")], {"on_time_probability": 0.92}, TODAY, TODAY)
    assert healthy["status"] == "On track"

    halted = build_report(PROJECT, [task("a", "Blocked")], {}, TODAY, TODAY)
    assert halted["status"] == "At risk" and any("halted" in reason for reason in halted["status_reasons"])

    doubtful = build_report(PROJECT, [task("a")], {"on_time_probability": 0.55}, TODAY, TODAY)
    assert doubtful["status"] == "At risk" and "55%" in " ".join(doubtful["status_reasons"])

    hopeless = build_report(PROJECT, [task("a")], {"on_time_probability": 0.2}, TODAY, TODAY)
    assert hopeless["status"] == "Late"

    passed = build_report({"name": "Old", "deadline": "2026-11-01"}, [task("a", end="2026-10-30")], {}, TODAY, TODAY)
    assert passed["status"] == "Late" and any("deadline has passed" in reason for reason in passed["status_reasons"])

    finished = build_report({"name": "Old", "deadline": "2026-11-01"}, [task("a", "Completed", end="2026-10-30")], {}, TODAY, TODAY)
    assert finished["status"] == "On track"


def test_a_past_week_is_judged_as_of_that_week():
    tasks = [task("a", "Pending", end="2026-11-12")]
    past = build_report(PROJECT, tasks, {}, date(2026, 11, 3), TODAY)   # week of 2 Nov, written on 12 Nov
    assert past["overdue"] == []                                         # was not late yet during that week
    now = build_report(PROJECT, tasks, {}, TODAY, date(2026, 11, 16))
    assert [t["id"] for t in now["overdue"]] == ["a"]


def test_risks_are_sorted_and_limited_to_three():
    risks = [{"severity": "Low", "message": "l1"}, {"severity": "High", "message": "h1"}, {"severity": "Medium", "message": "m1"},
             {"severity": "Medium", "message": "m2"}, "an old plain string risk"]
    report = build_report(PROJECT, [task("a")], {"risks": risks}, TODAY, TODAY)
    assert [r["message"] for r in report["risks"]] == ["h1", "m1", "m2"]


def test_markdown_is_readable_and_handles_empty_weeks():
    empty = build_report(PROJECT, [], {}, TODAY, TODAY)
    assert "Nothing completed this week." in empty["markdown"] and "No work is scheduled." in empty["markdown"]
    report = build_report(PROJECT, [task("a", "Completed", completed_at="2026-11-10T09:00:00"), task("b", "Blocked")],
                          {"on_time_probability": 0.8, "forecast_p50": "2026-12-10", "forecast_p85": "2026-12-14", "risks": [{"severity": "High", "message": "Big one"}]}, TODAY, TODAY)
    text = report["markdown"]
    for expected in ("# Weekly status: Billing", "## Completed this week", "- Task a (Ana)", "HALTED: Task b", "80% chance", "[High] Big one", "## Next week"):
        assert expected in text, expected


def test_endpoint_returns_a_report_for_a_real_plan(client):
    member = make_member(client, name="Ana")
    project_id, plan = make_plan(client, [member])
    client.patch(f"/api/tasks/{plan['tasks'][0]['id']}", json={"status": "Completed"})
    client.patch(f"/api/tasks/{plan['tasks'][1]['id']}", json={"status": "In Progress"})

    response = client.get(f"/api/projects/{project_id}/report", params={"today": "2026-11-03"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["project"] == "Replan" and body["week_start"] == "2026-11-02"
    assert body["progress"]["done"] == 1 and len(body["in_progress"]) == 1
    assert body["markdown"].startswith("# Weekly status: Replan")

    later = client.get(f"/api/projects/{project_id}/report", params={"today": "2026-11-03", "week": "2026-11-09"}).json()
    assert later["week_start"] == "2026-11-09"
    assert client.get(f"/api/projects/{project_id}/report", params={"week": "nope"}).status_code == 422
    assert client.get("/api/projects/9999/report").status_code == 404


# --- file downloads: Word, PDF, CSV ----------------------------------------------------------------------------

def _report_project(client):
    member = make_member(client, name="Ana")
    project_id, plan = make_plan(client, [member])
    client.patch(f"/api/tasks/{plan['tasks'][0]['id']}", json={"status": "Completed"})
    client.patch(f"/api/tasks/{plan['tasks'][1]['id']}", json={"status": "Blocked"})
    return project_id


def test_export_word_document(client):
    import io

    from docx import Document

    project_id = _report_project(client)
    response = client.get(f"/api/projects/{project_id}/report/export", params={"format": "docx", "today": "2026-11-03"})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert 'filename="weekly-report-replan-2026-11-02.docx"' in response.headers["content-disposition"]
    document = Document(io.BytesIO(response.content))  # a real, openable .docx
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "Weekly status: Replan" in text and "Completed this week" in text and "HALTED" in text and "Top risks" in text


def test_export_pdf_document(client):
    import pymupdf

    project_id = _report_project(client)
    response = client.get(f"/api/projects/{project_id}/report/export", params={"format": "pdf", "today": "2026-11-03"})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert response.headers["content-disposition"].endswith('.pdf"')
    pdf = pymupdf.open(stream=response.content, filetype="pdf")
    text = "".join(page.get_text() for page in pdf)
    assert pdf.page_count >= 1
    assert "Weekly status: Replan" in text and "Completed this week" in text and "Next week" in text


def test_export_csv_opens_in_excel_with_one_row_per_item(client):
    import csv
    import io

    project_id = _report_project(client)
    response = client.get(f"/api/projects/{project_id}/report/export", params={"format": "csv", "today": "2026-11-03"})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert response.content.startswith("﻿".encode("utf-8"))  # Excel-friendly byte order mark
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0] == ["Report", "Week", "Section", "Item", "Owner", "Status", "Due", "Hours"]
    sections = {row[2] for row in rows[1:]}
    assert {"Overview", "Blocked", "Top risks"} <= sections  # nothing finished inside the requested week
    assert all(len(row) == 8 and row[0] == "Replan" for row in rows[1:])
    blocked = next(row for row in rows if row[2] == "Blocked")
    assert blocked[4] == "Ana" and blocked[5] == "Blocked"


def test_export_validates_format_and_project(client):
    project_id = _report_project(client)
    assert client.get(f"/api/projects/{project_id}/report/export", params={"format": "exe"}).status_code == 422
    assert client.get("/api/projects/9999/report/export", params={"format": "pdf"}).status_code == 404
    assert client.get(f"/api/projects/{project_id}/report/export", params={"format": "pdf", "week": "bad"}).status_code == 422
    # the format name is case-insensitive and tolerates a leading dot
    assert client.get(f"/api/projects/{project_id}/report/export", params={"format": ".PDF"}).status_code == 200


def test_export_handles_empty_weeks_and_special_characters(client):
    import pymupdf

    member = make_member(client, name="Zoë <Dev> & Co")
    project_id, _plan = make_plan(client, [member])
    for fmt in ("docx", "pdf", "csv"):
        response = client.get(f"/api/projects/{project_id}/report/export", params={"format": fmt, "week": "2027-06-07"})
        assert response.status_code == 200, (fmt, response.text)
        assert len(response.content) > 200
    pdf = pymupdf.open(stream=client.get(f"/api/projects/{project_id}/report/export", params={"format": "pdf", "week": "2027-06-07"}).content, filetype="pdf")
    assert "Nothing completed this week." in "".join(page.get_text() for page in pdf)
