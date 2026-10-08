"""Overview: Sarah's Peak Academy dashboard mockup."""

from flask import g, render_template, request

from .. import metrics
from . import all_options, bp, period_from_args, records, visible_people

UPCOMING_DAYS = 30


@bp.route("/overview")
def overview():
    f = metrics.Filters.from_args(request.args)
    preset, start, end = period_from_args()
    ppl = visible_people(f)
    enr = metrics.enrollments(g.snap, ppl)
    mand = metrics.mandatory(enr)
    pdue = metrics.past_due(enr)
    upc = metrics.upcoming(enr, UPCOMING_DAYS)
    comp = metrics.completions(enr, start, end)
    heads = len(metrics.associates(ppl))
    hours = float(comp["TRAINING_MINUTES"].sum() / 60)

    kpi = {
        "compliance": metrics.associate_compliance(mand),
        "assignment_pct": metrics.totals(mand)["pct"],
        "past_due": {"n": len(pdue), "associates": pdue["LMS_USER_ID"].nunique(),
                     "avg_days": float(pdue["DAYS_PAST_DUE"].mean()) if len(pdue) else None},
        "upcoming": {"n": len(upc), "associates": upc["LMS_USER_ID"].nunique(),
                     "courses": upc["LMS_COURSE_ID"].nunique()},
        "completions": {"n": len(comp), "associates": comp["LMS_USER_ID"].nunique(),
                        "courses": comp["LMS_COURSE_ID"].nunique()},
        "hours": {"total": hours, "per_associate": hours / heads if heads else None, "headcount": heads},
    }
    by_loc = metrics.by_location(mand)
    prog = metrics.core_progress(g.snap, enr)
    plans = [p for p in metrics.core_plan_summary(g.snap, prog) if p["learners"]]
    worst = pdue.sort_values("DAYS_PAST_DUE", ascending=False).head(10)
    recent = comp.sort_values("DATETIME_COMPLETED", ascending=False).head(10)
    return render_template("overview.html", kpi=kpi, by_loc=by_loc, plans=plans,
                           worst=records(worst), recent=records(recent), options=all_options(),
                           f=f, period=preset, start=start, end=end, upcoming_days=UPCOMING_DAYS)
