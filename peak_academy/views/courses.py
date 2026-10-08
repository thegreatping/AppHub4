"""Course Details: catalog with learner activity -> one course's learners."""

from flask import abort, g, render_template, request

from .. import metrics
from . import all_options, bp, export, record, records, visible_people, wants_export


@bp.route("/courses")
def courses():
    f = metrics.Filters.from_args(request.args)
    enr = metrics.enrollments(g.snap, visible_people(f))
    stats = metrics.course_stats(g.snap, enr)
    show = request.args.get("show", "active")
    if show == "active":
        stats = stats[stats["enrolled"] > 0]
    elif show == "published":
        stats = stats[stats["FLAG_PUBLISHED"] == 1]
    stats = stats.sort_values(["enrolled", "COURSE_TITLE"], ascending=[False, True])
    rows = records(stats)
    if wants_export():
        cols = [("COURSE_TITLE", "Course"), ("COURSE_TYPE", "Type"), ("DURATION_IN_MINUTES", "Minutes"),
                ("core_plans", "CORE Plans"), ("enrolled", "Enrolled"), ("in_progress", "In Progress"),
                ("completed", "Completed"), ("completion_pct", "Completion %"), ("past_due", "Past Due")]
        return export(rows, cols, "course_details")
    return render_template("courses.html", rows=rows, show=show, options=all_options(), f=f)


@bp.route("/courses/<cid>")
def course(cid):
    c = g.snap.courses[g.snap.courses["LMS_COURSE_ID"] == cid]
    if c.empty:
        abort(404)
    enr = metrics.enrollments(g.snap, visible_people())
    learners = metrics.assignment_order(metrics.assignments(enr)[lambda d: d["LMS_COURSE_ID"] == cid])
    rows = records(learners)
    plans = g.snap.plan_courses[g.snap.plan_courses["LMS_COURSE_ID"] == cid]
    if wants_export():
        cols = [("NAME_FULL", "Associate"), ("PROPERTY_NAME", "Location"), ("JOB_TITLE", "Job Title"),
                ("COURSE_PASSING_STATUS", "Progress"), ("DATETIME_DUE", "Due"),
                ("DATETIME_COMPLETED", "Completed"), ("COMPLIANCE_STATUS", "Compliance")]
        return export(rows, cols, "course_learners")
    return render_template("course.html", course=record(c.iloc[0]), rows=rows,
                           plans=records(plans), totals=metrics.totals(metrics.mandatory(learners)))
