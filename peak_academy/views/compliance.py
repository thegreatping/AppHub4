"""Training Compliance (Sarah's #1 report, "Location Compliance"): locations -> associates."""

from flask import abort, g, redirect, render_template, request, url_for

from .. import metrics
from . import all_options, bp, export, record, visible_people, wants_export

COUNT_COLS = [("associates", "Associates"), ("assigned", "Assigned"), ("compliant", "Compliant"),
              ("not_compliant", "Past Due"), ("pct", "Compliance %")]


@bp.route("/compliance")
def locations():
    f = metrics.Filters.from_args(request.args)
    df = metrics.mandatory(metrics.enrollments(g.snap, visible_people(f)))
    rows = metrics.by_location(df)
    if wants_export():
        cols = [("property_name", "Location"), ("rvp_name", "RVP"), ("rm_name", "RM"),
                ("pm_name", "PM")] + COUNT_COLS
        return export(rows, cols, "location_compliance")
    return render_template("locations.html", rows=rows, totals=metrics.totals(df),
                           options=all_options(), f=f)


@bp.route("/compliance/location/<int:key>")
def location(key):
    if not g.viewer.can_see(key):
        abort(403)
    df = metrics.mandatory(metrics.enrollments(g.snap, visible_people(metrics.Filters(property_key=key))))
    rows = metrics.by_associate(df)
    name = rows[0]["property_name"] if rows else metrics.UNASSIGNED_NAME
    if wants_export():
        cols = [("name", "Associate"), ("email", "Email"), ("job_title", "Job Title"),
                ("assigned", "Assigned"), ("compliant", "Compliant"), ("not_compliant", "Past Due"),
                ("max_days_past_due", "Max Days Past Due"), ("pct", "Compliance %")]
        return export(rows, cols, "associate_compliance")
    return render_template("location.html", key=key, name=name, rows=rows,
                           totals=metrics.totals(df), info=record(df.iloc[0]) if len(df) else None)


@bp.route("/compliance/associate/<uid>")
def associate(uid):
    return redirect(url_for("lms.person", uid=uid), code=301)
