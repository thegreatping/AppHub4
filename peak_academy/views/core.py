"""CORE Onboarding: the "CORE - <role>" training plans and each learner's progress."""

from flask import abort, g, render_template, request

from .. import metrics
from . import all_options, bp, export, records, visible_people, wants_export


def _progress(f=None):
    enr = metrics.enrollments(g.snap, visible_people(f))
    return enr, metrics.core_progress(g.snap, enr)


@bp.route("/core")
def core():
    f = metrics.Filters.from_args(request.args)
    enr, prog = _progress(f)
    plans = metrics.core_plan_summary(g.snap, prog)
    return render_template("core.html", plans=plans, learners=len(prog), options=all_options(), f=f)


@bp.route("/core/<plan_id>")
def core_plan(plan_id):
    items = g.snap.plan_courses[g.snap.plan_courses["LMS_TRAINING_PLAN_ID"] == plan_id]
    if items.empty:
        abort(404)
    enr, prog = _progress()
    prog = prog[prog["LMS_TRAINING_PLAN_ID"] == plan_id].sort_values(["PCT", "NAME_FULL"])
    rows = records(prog)
    if wants_export():
        for r in rows:
            r["HOURS_LEFT"] = r["MINUTES_LEFT"] / 60
            r["BEHIND"] = "Yes" if r["FLAG_BEHIND"] else ""
        cols = [("NAME_FULL", "Associate"), ("PROPERTY_NAME", "Location"), ("JOB_TITLE", "Job Title"),
                ("PLAN_STATUS", "Plan Status"), ("COURSES_DONE", "Courses Done"),
                ("COURSES_TOTAL", "Courses in Plan"), ("PCT", "Complete %"),
                ("DATETIME_REGISTERED", "Enrolled"), ("DATETIME_DUE", "Due"), ("HOURS_LEFT", "Hours Left"),
                ("WORKDAYS_LEFT", "Workdays Left"), ("HOURS_PER_DAY", "Hours/Day Needed"), ("BEHIND", "Behind")]
        return export(rows, cols, "core_plan_progress")
    return render_template("core_plan.html", title=items.iloc[0]["TRAINING_PLAN_TITLE"].strip(),
                           plan_id=plan_id, rows=rows, behind=int(prog["FLAG_BEHIND"].sum()),
                           budget=metrics.core_budget_label(),
                           courses=metrics.core_course_rates(g.snap, plan_id, prog, enr))
