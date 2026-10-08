"""Office Locations: training activity by location (headcount, completions, hours, due)."""

from flask import g, render_template, request

from .. import metrics
from . import all_options, bp, export, period_from_args, visible_people, wants_export


@bp.route("/locations")
def offices():
    f = metrics.Filters.from_args(request.args)
    preset, start, end = period_from_args()
    ppl = visible_people(f)
    rows = metrics.location_stats(ppl, metrics.enrollments(g.snap, ppl), start, end)
    if wants_export():
        cols = [("property_name", "Location"), ("rvp_name", "RVP"), ("rm_name", "RM"),
                ("associates", "Associates"), ("completions", "Completions (period)"),
                ("hours", "Training Hours (period)"), ("hours_per_associate", "Hours / Associate"),
                ("past_due", "Past Due"), ("upcoming", "Due Next 30 Days"), ("pct", "Compliance %")]
        return export(rows, cols, "office_locations")
    return render_template("offices.html", rows=rows, options=all_options(), f=f, period=preset)
