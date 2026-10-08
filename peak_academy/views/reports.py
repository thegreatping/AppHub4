"""Reports: Sarah's list of Grace Hill replacements, one generic table page each.

Every built report is a function (ppl, enr, args) -> (rows, columns). Columns are
(key, header, kind); kind drives formatting in report.html: text | num | pct | bar |
date | hours | status | progress. A row may carry "_href": {key: url} to link a cell.
"""

from dataclasses import dataclass, field
from datetime import date

from flask import abort, g, redirect, render_template, request, url_for

from .. import metrics
from . import all_options, bp, export, period_from_args, records, require_admin, visible_people, wants_export


@dataclass
class Report:
    slug: str
    title: str
    audience: str               # "Managers" | "Admin" (from Sarah's table)
    ask: str                    # Sarah's description, verbatim intent
    status: str = "built"       # built | link | blocked
    controls: list = field(default_factory=list)
    run: object = None
    link: str = None            # endpoint, for status == "link"
    blocked_by: str = ""        # why it can't be built yet
    note: str = ""              # provisional definitions this report relies on


def _links(rows, uid_key="LMS_USER_ID", course_key="LMS_COURSE_ID"):
    for r in rows:
        r["_href"] = {"NAME_FULL": url_for("lms.person", uid=r[uid_key])}
        if course_key in r and r.get(course_key):
            r["_href"]["COURSE_TITLE"] = url_for("lms.course", cid=r[course_key])
    return rows


def _days_arg(default=30):
    try:
        return max(0, int(request.args.get("days", default)))
    except ValueError:
        return default


# --------------------------------------------------------------------------- report bodies

def all_inclusive(ppl, enr, args):
    days = _days_arg()
    a = metrics.assignments(enr)
    a = a[a["FLAG_COMPLETED"] == 0]
    due_soon = a["DAYS_TO_DUE"].between(0, days) | a["DAYS_PAST_DUE"].notna()
    if args.get("undated"):
        due_soon |= a["DATETIME_DUE"].isna()
    a = metrics.assignment_order(a[due_soon])
    cols = [("NAME_FULL", "Associate", "text"), ("PROPERTY_NAME", "Location", "text"),
            ("GROUP_TYPE", "Role", "text"), ("COURSE_TITLE", "Course", "text"),
            ("COURSE_PASSING_STATUS", "Progress", "progress"), ("DATETIME_DUE", "Due", "date"),
            ("DAYS_PAST_DUE", "Days Past Due", "num"), ("DAYS_TO_DUE", "Days To Due", "num"),
            ("COMPLIANCE_STATUS", "Compliance", "status")]
    return _links(records(a)), cols


def core_report(ppl, enr, args):
    prog = metrics.core_progress(g.snap, enr).sort_values(["PLAN_TITLE", "PCT", "NAME_FULL"])
    rows = records(prog)
    for r in rows:
        r["BEHIND"] = "Behind" if r["FLAG_BEHIND"] else "On track" if r["HOURS_PER_DAY"] is not None else ""
        r["_href"] = {"NAME_FULL": url_for("lms.person", uid=r["LMS_USER_ID"]),
                      "PLAN_TITLE": url_for("lms.core_plan", plan_id=r["LMS_TRAINING_PLAN_ID"])}
    cols = [("NAME_FULL", "Associate", "text"), ("PROPERTY_NAME", "Location", "text"),
            ("JOB_TITLE", "Job Title", "text"), ("PLAN_TITLE", "CORE Plan", "text"),
            ("PLAN_STATUS", "Plan Status", "progress"), ("COURSES_DONE", "Courses Done", "num"),
            ("COURSES_TOTAL", "Courses in Plan", "num"), ("PCT", "Complete", "bar"),
            ("DATETIME_REGISTERED", "Enrolled", "date"), ("DATETIME_DUE", "Due", "date"),
            ("HOURS_PER_DAY", "Hours/Day Needed", "hours"), ("BEHIND", "Pace", "text")]
    return rows, cols


def completions_report(ppl, enr, args):
    _, start, end = period_from_args()
    try:
        if args.get("start"):
            start = date.fromisoformat(args["start"])
        if args.get("end"):
            end = date.fromisoformat(args["end"])
    except ValueError:
        pass
    c = metrics.completions(enr, start, end)
    q = (args.get("q") or "").strip().lower()
    if q:
        c = c[c["NAME_FULL"].str.lower().str.contains(q, na=False) | c["EMAIL"].str.lower().str.contains(q, na=False)]
    c = c.sort_values("DATETIME_COMPLETED", ascending=False).assign(
        TIMING=lambda d: d["FLAG_COMPLETED_LATE"].map({1: "Late", 0: "On time"}),
        HOURS=lambda d: d["TRAINING_MINUTES"] / 60)
    cols = [("NAME_FULL", "Associate", "text"), ("PROPERTY_NAME", "Location", "text"),
            ("COURSE_TITLE", "Course", "text"), ("DATETIME_COMPLETED", "Completed", "date"),
            ("DATETIME_DUE", "Due", "date"), ("TIMING", "On Time?", "text"), ("HOURS", "Hours", "hours")]
    return _links(records(c)), cols


def exclusions(ppl, enr, args):
    p = metrics.overdue(enr).sort_values(["DAYS_PAST_DUE", "NAME_FULL"], ascending=[False, True])
    cols = [("NAME_FULL", "Associate", "text"), ("PROPERTY_NAME", "Location", "text"),
            ("RM_NAME", "RM", "text"), ("COURSE_TITLE", "Course", "text"),
            ("COURSE_PASSING_STATUS", "Progress", "progress"), ("DATETIME_DUE", "Due", "date"),
            ("DAYS_PAST_DUE", "Days Overdue", "num"), ("COMPLIANCE_STATUS", "Compliance", "status")]
    return _links(records(p)), cols


def zero_assignments(ppl, enr, args):
    has = set(metrics.assignments(enr)["LMS_USER_ID"])
    z = metrics.associates(ppl)
    z = z[~z["LMS_USER_ID"].isin(has)].sort_values(["PROPERTY_NAME", "NAME_FULL"])
    cols = [("NAME_FULL", "Associate", "text"), ("EMAIL", "Email", "text"),
            ("PROPERTY_NAME", "Location", "text"), ("GROUP_TYPE", "Role", "text"),
            ("JOB_TITLE", "Job Title", "text"), ("DATETIME_HIRED", "Hired", "date"),
            ("EMPLOYEE_STATUS", "Status", "text")]
    return _links(records(z)), cols


def training_hours(ppl, enr, args):
    _, start, end = period_from_args()
    s = metrics.person_stats(ppl, enr, start, end)
    if not args.get("zeros"):
        s = s[s["completed"] > 0]
    s = s.sort_values(["hours", "NAME_FULL"], ascending=[False, True])
    cols = [("NAME_FULL", "Associate", "text"), ("PROPERTY_NAME", "Location", "text"),
            ("GROUP_TYPE", "Role", "text"), ("completed", "Courses Completed", "num"),
            ("hours", "Training Hours", "hours")]
    return _links(records(s)), cols


REPORTS = [
    Report("location-compliance", "Location Compliance", "Managers",
           "Mandatory assignments not past due ÷ all mandatory assignments, for every location, "
           "drilling to each associate.", status="link", link="lms.locations"),
    Report("all-inclusive", "All Inclusive Training Report", "Managers",
           "Open assignments, with the due-date window filterable any number of days into the future.",
           controls=["property", "role", "days", "undated"], run=all_inclusive,
           note="Includes everything already past due, plus open assignments due within the window."),
    Report("core-progress", "CORE Progress Report", "Managers",
           "All active CORE training plans with percentage of completion.",
           controls=["property", "role"], run=core_report,
           note="A plan course counts as done when the learner has completed it by any route. \"Behind\" = the "
                f"course time left is more than {metrics.core_budget_label()} per workday until the due date "
                "(placeholder)."),
    Report("course-completions", "Course Completions", "Managers",
           "All course completions, filterable by property, associate and date.",
           controls=["property", "role", "period", "dates", "q"], run=completions_report),
    Report("exclusions", "Exclusions Report", "Admin",
           "Employees' overdue assignments with the number of days they've been overdue.",
           controls=["property", "role"], run=exclusions,
           note="\"Overdue\" = any open assignment past its due date (Eastern time)."),
    Report("zero-assignments", "Zero Training Assignments", "Admin",
           "Employees who have no trainings at all assigned to them.",
           controls=["property", "role"], run=zero_assignments,
           note="Employees = LMS users matched to an Active / On Leave Paycom employee record."),
    Report("training-hours", "Training Hours Report", "Managers",
           "How many seat hours each employee has spent learning in the system.",
           controls=["property", "role", "period", "zeros"], run=training_hours,
           note="Hours = each completed course's catalog duration, credited on its completion date "
                "(not measured seat time)."),
    Report("exceptions", "Exceptions Report", "Admin",
           "Trainings an employee has been excluded from by an Admin.", status="blocked",
           blocked_by="The LMS extract has no record of admin exclusions. Zensai's Assignments feed, "
                      "the likely source, came back empty. Needs Rohit / Zensai to confirm where "
                      "exclusions live in the API."),
    Report("questions-answers", "Questions & Answers Report", "Admin",
           "A quiz's questions, each learner's answer, the correct answer, and points awarded.",
           status="blocked",
           blocked_by="The extract truncates text at 4,000 characters, which cuts 15 of 17 quizzes' "
                      "question lists mid-JSON (Rohit). Sarah also flagged that Learn365's automation "
                      "center might cover this without BI, so confirm it's still wanted."),
]
BY_SLUG = {r.slug: r for r in REPORTS}

# Rows rendered on screen; exports always carry everything.
SCREEN_ROWS = 2000


@bp.route("/reports")
def reports():
    return render_template("reports.html", reports=REPORTS)


@bp.route("/reports/<slug>")
def report(slug):
    rep = BY_SLUG.get(slug)
    if rep is None:
        abort(404)
    if rep.status == "link":
        return redirect(url_for(rep.link))
    if rep.audience == "Admin":
        require_admin()
    if rep.status == "blocked":
        return render_template("report.html", rep=rep, rows=[], total=0, columns=[], options={}, f=None)
    f = metrics.Filters.from_args(request.args)
    ppl = visible_people(f)
    rows, columns = rep.run(ppl, metrics.enrollments(g.snap, ppl), request.args)
    if wants_export():
        return export(rows, columns, slug.replace("-", "_"))
    preset, start, end = period_from_args()
    return render_template("report.html", rep=rep, rows=rows[:SCREEN_ROWS], total=len(rows),
                           columns=columns, options=all_options(),
                           f=f, period=preset, start=start, end=end, days=_days_arg())
