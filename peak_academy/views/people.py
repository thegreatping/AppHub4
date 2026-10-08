"""Associate Training: directory -> one associate's full training record."""

from flask import abort, g, render_template, request

from .. import metrics
from . import all_options, bp, export, period_from_args, record, records, visible_people, wants_export


@bp.route("/associates")
def people():
    f = metrics.Filters.from_args(request.args)
    preset, start, end = period_from_args(default="all")
    ppl = visible_people(f)
    stats = metrics.person_stats(ppl, metrics.enrollments(g.snap, ppl), start, end)
    stats = stats.sort_values(["past_due", "NAME_FULL"], ascending=[False, True])
    rows = records(stats)
    if wants_export():
        cols = [("NAME_FULL", "Associate"), ("EMAIL", "Email"), ("PROPERTY_NAME", "Location"),
                ("GROUP_TYPE", "Role"), ("JOB_TITLE", "Job Title"), ("assigned", "Assigned"),
                ("open", "Open"), ("past_due", "Past Due"), ("completed", "Completed (period)"),
                ("hours", "Training Hours (period)"), ("mandatory", "Mandatory Assignments"),
                ("compliance_pct", "Compliance %")]
        return export(rows, cols, "associate_training")
    return render_template("people.html", rows=rows, options=all_options(), f=f, period=preset)


@bp.route("/associates/<uid>")
def person(uid):
    users = g.snap.users[g.snap.users["LMS_USER_ID"] == uid]
    if users.empty:
        abort(404)
    user = record(users.iloc[0])
    key = int(user["PROPERTY_KEY"]) if user["PROPERTY_KEY"] is not None else metrics.UNASSIGNED_KEY
    if not g.viewer.can_see(key):
        abort(403)
    ppl = visible_people()
    enr = metrics.enrollments(g.snap, ppl[ppl["LMS_USER_ID"] == uid])
    work = metrics.assignment_order(metrics.assignments(enr))
    rows = records(work)
    if wants_export():
        cols = [("COURSE_TITLE", "Course"), ("COMPLIANCE_STATUS", "Compliance"),
                ("COURSE_PASSING_STATUS", "Progress"), ("DATETIME_REGISTERED", "Enrolled"),
                ("DATETIME_DUE", "Due"), ("DATETIME_COMPLETED", "Completed"),
                ("DAYS_PAST_DUE", "Days Past Due"), ("TRAINING_MINUTES", "Minutes Credited")]
        return export(rows, cols, "associate_training_record")
    comp = work[work["FLAG_COMPLETED"] == 1]
    return render_template(
        "person.html", user=user, key=key, rows=rows,
        totals=metrics.totals(metrics.mandatory(enr)),
        hours=float(comp["TRAINING_MINUTES"].sum() / 60),
        plans=records(metrics.core_progress(g.snap, enr)))
