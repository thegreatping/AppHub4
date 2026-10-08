"""Roll-ups for every tab. Pure pandas, no Flask, so they can be unit tested.

Per-enrollment rules (mandatory, scope, compliant, training minutes) are decided in the
warehouse (LMS_ENROLLMENTS_0_SP). This module only filters and counts. The few
app-level definitions that are still provisional are marked PROVISIONAL and listed on
the Definitions page.

Pipeline for every view:  people(snap, viewer scope, filters) -> enrollments(snap, people)
"""

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

UNASSIGNED_KEY = -1
UNASSIGNED_NAME = "Unassigned"

STATUS_ORDER = ["NOT COMPLIANT", "COMPLIANCE ACHIEVABLE", "COMPLETED LATE", "COMPLETED ON TIME"]

# PROVISIONAL: which LMS users count as "associates" (headcount, zero-assignment report).
ACTIVE_EMPLOYEE_STATUSES = {"ACTIVE", "ON LEAVE"}

# PROVISIONAL (S22): CORE "behind" flag. Training time a learner is expected to fit in per
# workday (Mon-Fri). Placeholder until L&D sets the number.
CORE_DAILY_BUDGET_MINUTES = 60


def core_budget_label():
    """The budget in words, e.g. "1 hour", for definitions and notes."""
    h = CORE_DAILY_BUDGET_MINUTES / 60
    return f"{h:g} hour{'s' if h != 1 else ''}"


# --------------------------------------------------------------------------- periods

PERIODS = [("this_month", "This month"), ("this_quarter", "This quarter"), ("ytd", "Year to date"),
           ("last_30", "Last 30 days"), ("last_90", "Last 90 days"), ("all", "All time")]


def period_bounds(preset, today):
    """(start, end) dates, inclusive; start None = no lower bound."""
    if preset == "this_month":
        return today.replace(day=1), today
    if preset == "this_quarter":
        return date(today.year, 3 * ((today.month - 1) // 3) + 1, 1), today
    if preset == "ytd":
        return date(today.year, 1, 1), today
    if preset == "last_30":
        return today - timedelta(days=29), today
    if preset == "last_90":
        return today - timedelta(days=89), today
    return None, today


def in_period(series, start, end):
    # Compare as midnight Timestamps, not .dt.date: on an all-NaT series .dt.date stays
    # datetime64, and datetime64 <= date raises (e.g. a role with no completions yet).
    d = pd.to_datetime(series).dt.normalize()
    ok = d.notna() & (d <= pd.Timestamp(end))
    if start is not None:
        ok &= d >= pd.Timestamp(start)
    return ok


# --------------------------------------------------------------------------- filters

@dataclass
class Filters:
    property_key: int = None
    property_type: str = None
    rvp: str = None
    rm: str = None
    role: str = None

    @classmethod
    def from_args(cls, args):
        key = args.get("property")
        return cls(property_key=int(key) if key not in (None, "") else None,
                   property_type=args.get("property_type") or None, rvp=args.get("rvp") or None,
                   rm=args.get("rm") or None, role=args.get("role") or None)

    def active(self):
        return any(v is not None for v in vars(self).values())


# --------------------------------------------------------------------------- base frames

def people(snap, allowed_keys=None, f=None):
    """Visible, non-deleted LMS users with an int PROPERTY_KEY (-1 = unassigned)."""
    u = snap.users[snap.users["FLAG_DELETED"] == 0].copy()
    u["PROPERTY_KEY"] = u["PROPERTY_KEY"].fillna(UNASSIGNED_KEY).astype(int)
    u["PROPERTY_NAME"] = u["PROPERTY_NAME"].fillna(UNASSIGNED_NAME)
    if allowed_keys is not None:
        u = u[u["PROPERTY_KEY"].isin(allowed_keys)]
    if f is not None:
        if f.property_key is not None:
            u = u[u["PROPERTY_KEY"] == f.property_key]
        if f.property_type:
            u = u[u["PROPERTY_TYPE_LMS"] == f.property_type]
        if f.rvp:
            u = u[u["RVP_NAME"] == f.rvp]
        if f.rm:
            u = u[u["RM_NAME"] == f.rm]
        if f.role:
            u = u[u["GROUP_TYPE"] == f.role]
    return u


def associates(ppl):
    """PROVISIONAL: headcount = users matched to an active / on-leave Paycom employee."""
    return ppl[(ppl["FLAG_EMPLOYEE_MATCH"] == 1) & ppl["EMPLOYEE_STATUS"].isin(ACTIVE_EMPLOYEE_STATUSES)]


def enrollments(snap, ppl):
    """Every enrollment of the given people, with their user attributes."""
    return snap.facts.merge(ppl, on="LMS_USER_ID", how="inner", suffixes=("", "_USER"))


def assignments(enr):
    """Course-level learner assignments: learner role, not cancelled, not a CORE plan wrapper."""
    return enr[(enr["FLAG_LEARNER"] == 1) & (enr["FLAG_CANCELLED"] == 0) & (enr["COURSE_TYPE"] != "TrainingPlan")]


def mandatory(enr):
    return enr[enr["FLAG_COMPLIANCE_SCOPE"] == 1]


def scoped(snap, allowed_keys=None, f=None):
    """In-scope (mandatory) enrollments of visible people. Kept for the compliance views."""
    return mandatory(enrollments(snap, people(snap, allowed_keys, f)))


def completions(enr, start, end):
    a = assignments(enr)
    return a[(a["FLAG_COMPLETED"] == 1) & in_period(a["DATETIME_COMPLETED"], start, end)]


def upcoming(enr, days):
    """Open assignments due within `days` (0 = due today)."""
    a = assignments(enr)
    return a[(a["FLAG_COMPLETED"] == 0) & a["DAYS_TO_DUE"].between(0, days)]


def past_due(enr):
    return mandatory(enr)[lambda d: d["COMPLIANCE_STATUS"] == "NOT COMPLIANT"]


def overdue(enr):
    """Any open course assignment past its due date, mandatory or not (Exclusions report)."""
    a = assignments(enr)
    return a[a["FLAG_PAST_DUE"] == 1]


# --------------------------------------------------------------------------- compliance roll-ups

def _counts(df):
    assigned = len(df)
    compliant = int(df["FLAG_COMPLIANT"].sum()) if assigned else 0
    return {
        "associates": df["LMS_USER_ID"].nunique(),
        "assigned": assigned,
        "compliant": compliant,
        "not_compliant": assigned - compliant,
        "achievable": int((df["COMPLIANCE_STATUS"] == "COMPLIANCE ACHIEVABLE").sum()),
        "completed": int(df["FLAG_COMPLETED"].sum()) if assigned else 0,
        "pct": compliant / assigned if assigned else None,
    }


def totals(df):
    return _counts(df)


def associate_compliance(mand):
    """PROVISIONAL: an associate is compliant when none of their mandatory assignments is past due."""
    if mand.empty:
        return {"compliant": 0, "not_compliant": 0, "total": 0, "pct": None}
    bad = mand.groupby("LMS_USER_ID")["FLAG_COMPLIANT"].min()
    total, ok = len(bad), int((bad == 1).sum())
    return {"compliant": ok, "not_compliant": total - ok, "total": total, "pct": ok / total}


def by_location(df):
    """One row per property: counts, %, and its PM / RM / RVP. Worst compliance first."""
    rows = []
    for key, g in df.groupby("PROPERTY_KEY", sort=False):
        first = g.iloc[0]
        rows.append({
            "property_key": int(key),
            "property_name": first["PROPERTY_NAME"],
            "pm_name": first["PM_NAME"],
            "rm_name": first["RM_NAME"],
            "rvp_name": first["RVP_NAME"],
            **_counts(g),
        })
    rows.sort(key=lambda r: (r["pct"] if r["pct"] is not None else 2, r["property_name"]))
    return rows


def by_associate(df):
    """One row per associate at whatever locations df covers. Worst compliance first."""
    rows = []
    for uid, g in df.groupby("LMS_USER_ID", sort=False):
        first = g.iloc[0]
        c = _counts(g)
        overdue = g["DAYS_PAST_DUE"].dropna()
        rows.append({
            "lms_user_id": uid,
            "name": first["NAME_FULL"],
            "email": first["EMAIL"],
            "job_title": first["JOB_TITLE"],
            "property_key": int(first["PROPERTY_KEY"]),
            "property_name": first["PROPERTY_NAME"],
            "max_days_past_due": int(overdue.max()) if len(overdue) else None,
            **c,
        })
    rows.sort(key=lambda r: (r["pct"] if r["pct"] is not None else 2, r["name"] or ""))
    return rows


def assignment_order(df):
    """Past due first (most overdue on top), then soonest due, then the rest."""
    order = {s: i for i, s in enumerate(STATUS_ORDER)}
    out = df.assign(_o=df["COMPLIANCE_STATUS"].map(order).fillna(len(order)),
                    _p=-df["DAYS_PAST_DUE"].fillna(-1),
                    _d=df["DAYS_TO_DUE"].fillna(10**6))
    return out.sort_values(["_o", "_p", "_d", "COURSE_TITLE"]).drop(columns=["_o", "_p", "_d"])


# --------------------------------------------------------------------------- CORE training plans

def plan_course_minutes(snap):
    """Expected minutes for each (plan, course): the catalog duration, or where the catalog has
    none (or 0) the average of the plan's other courses."""
    pc = snap.plan_courses[["LMS_TRAINING_PLAN_ID", "LMS_COURSE_ID"]].drop_duplicates()
    c = snap.courses
    dur = (c.drop_duplicates("LMS_COURSE_ID").set_index("LMS_COURSE_ID")["DURATION_IN_MINUTES"]
           if "DURATION_IN_MINUTES" in c.columns else pd.Series(dtype=float))
    m = pc["LMS_COURSE_ID"].map(dur).astype(float)
    m = m.where(m > 0)
    m = m.fillna(m.groupby(pc["LMS_TRAINING_PLAN_ID"]).transform("mean")).fillna(m.mean())
    return pc.assign(MINUTES=m.fillna(0).astype(float))


def core_progress(snap, enr, budget_minutes=CORE_DAILY_BUDGET_MINUTES):
    """One row per (learner, CORE plan enrollment) with courses completed / plan size, and pace.

    Progress counts a plan course as done when the learner has ANY completed enrollment in
    it, whether or not that enrollment came through the plan.

    Pace (PROVISIONAL, S22): MINUTES_LEFT is the expected time of the plan courses not yet done;
    WORKDAYS_LEFT counts Mon-Fri from the as-of date through the plan's due date; HOURS_PER_DAY
    is what the learner must average to finish on time. FLAG_BEHIND = 1 when that is more than
    budget_minutes a day, including a plan that is past due or has no workdays left. A plan with
    no due date is never flagged.
    """
    plans = enr[(enr["COURSE_TYPE"] == "TrainingPlan") & (enr["FLAG_LEARNER"] == 1) & (enr["FLAG_CANCELLED"] == 0)]
    if plans.empty or snap.plan_courses.empty:
        return pd.DataFrame(columns=["LMS_USER_ID", "LMS_TRAINING_PLAN_ID", "PLAN_TITLE", "COURSES_TOTAL",
                                     "COURSES_DONE", "PCT", "PLAN_STATUS", "NAME_FULL", "PROPERTY_KEY",
                                     "PROPERTY_NAME", "JOB_TITLE", "DATETIME_REGISTERED", "DATETIME_DUE",
                                     "MINUTES_LEFT", "WORKDAYS_LEFT", "HOURS_PER_DAY", "FLAG_BEHIND"])
    size = snap.plan_courses.groupby("LMS_TRAINING_PLAN_ID")["LMS_COURSE_ID"].nunique()
    done = enr[enr["FLAG_COMPLETED"] == 1][["LMS_USER_ID", "LMS_COURSE_ID"]].drop_duplicates()
    hit = (plans[["LMS_USER_ID", "LMS_COURSE_ID"]]
           .rename(columns={"LMS_COURSE_ID": "LMS_TRAINING_PLAN_ID"})
           .merge(snap.plan_courses[["LMS_TRAINING_PLAN_ID", "LMS_COURSE_ID"]], on="LMS_TRAINING_PLAN_ID")
           .merge(done, on=["LMS_USER_ID", "LMS_COURSE_ID"])
           .groupby(["LMS_USER_ID", "LMS_TRAINING_PLAN_ID"]).size())
    out = plans.rename(columns={"LMS_COURSE_ID": "LMS_TRAINING_PLAN_ID", "COURSE_TITLE": "PLAN_TITLE",
                                "COURSE_PASSING_STATUS": "PLAN_STATUS"}).copy()
    out["PLAN_TITLE"] = out["PLAN_TITLE"].str.strip()
    out["COURSES_TOTAL"] = out["LMS_TRAINING_PLAN_ID"].map(size).fillna(0).astype(int)
    out["COURSES_DONE"] = [int(hit.get((u, p), 0)) for u, p in zip(out["LMS_USER_ID"], out["LMS_TRAINING_PLAN_ID"])]
    out["PCT"] = (out["COURSES_DONE"] / out["COURSES_TOTAL"]).where(out["COURSES_TOTAL"] > 0)

    left = (plans[["LMS_USER_ID", "LMS_COURSE_ID"]].drop_duplicates()
            .rename(columns={"LMS_COURSE_ID": "LMS_TRAINING_PLAN_ID"})
            .merge(plan_course_minutes(snap), on="LMS_TRAINING_PLAN_ID")
            .merge(done.assign(_done=1), on=["LMS_USER_ID", "LMS_COURSE_ID"], how="left"))
    left = left[left["_done"].isna()].groupby(["LMS_USER_ID", "LMS_TRAINING_PLAN_ID"])["MINUTES"].sum()
    out["MINUTES_LEFT"] = [float(left.get((u, p), 0.0))
                           for u, p in zip(out["LMS_USER_ID"], out["LMS_TRAINING_PLAN_ID"])]

    today = np.datetime64(snap.as_of or date.today(), "D")
    due = pd.to_datetime(out["DATETIME_DUE"]).dt.normalize()
    has_due = due.notna()
    workdays = pd.Series(np.nan, index=out.index)
    if has_due.any():
        # busday_count is end-exclusive, so +1 day makes the due date itself a workday.
        ends = (due[has_due] + pd.Timedelta(days=1)).values.astype("datetime64[D]")
        workdays[has_due] = np.maximum(np.busday_count(today, ends), 0)
    open_ = out["MINUTES_LEFT"] > 0
    out["WORKDAYS_LEFT"] = workdays
    out["HOURS_PER_DAY"] = (out["MINUTES_LEFT"] / 60 / workdays).where(open_ & (workdays > 0))
    out["FLAG_BEHIND"] = (has_due & open_ & (out["MINUTES_LEFT"] > workdays.fillna(0) * budget_minutes)).astype(int)
    return out


def core_plan_summary(snap, prog):
    """One row per CORE plan: size, learners, fully complete, average progress."""
    plans = snap.plan_courses.groupby(["LMS_TRAINING_PLAN_ID", "TRAINING_PLAN_TITLE"])["LMS_COURSE_ID"].nunique()
    rows = []
    for (pid, title), n in plans.items():
        p = prog[prog["LMS_TRAINING_PLAN_ID"] == pid]
        rows.append({"plan_id": pid, "title": title.strip(), "courses": int(n), "learners": len(p),
                     "complete": int((p["PCT"] >= 1).sum()) if len(p) else 0,
                     "behind": int((p["FLAG_BEHIND"] == 1).sum()) if len(p) else 0,
                     "avg_pct": float(p["PCT"].mean()) if len(p) else None})
    rows.sort(key=lambda r: r["title"])
    return rows


def core_course_rates(snap, plan_id, prog, enr):
    """Within one plan: completion rate of each course among the plan's learners, in plan order."""
    learners = set(prog.loc[prog["LMS_TRAINING_PLAN_ID"] == plan_id, "LMS_USER_ID"])
    done = enr[(enr["FLAG_COMPLETED"] == 1) & enr["LMS_USER_ID"].isin(learners)]
    items = snap.plan_courses[snap.plan_courses["LMS_TRAINING_PLAN_ID"] == plan_id].sort_values("COURSE_ORDER")
    rows = []
    for _, it in items.iterrows():
        n = done.loc[done["LMS_COURSE_ID"] == it["LMS_COURSE_ID"], "LMS_USER_ID"].nunique()
        rows.append({"order": int(it["COURSE_ORDER"]), "course_id": it["LMS_COURSE_ID"],
                     "title": it["COURSE_TITLE"], "done": n,
                     "pct": n / len(learners) if learners else None})
    return rows


# --------------------------------------------------------------------------- courses / people / locations

def course_stats(snap, enr):
    """One row per published, non-deleted, non-plan course, with learner activity."""
    c = snap.courses[(snap.courses["FLAG_DELETED"] == 0) & (snap.courses["COURSE_TYPE"] != "TrainingPlan")]
    a = assignments(enr)
    g = a.groupby("LMS_COURSE_ID")
    stats = pd.DataFrame({
        "enrolled": g.size(),
        "in_progress": g["COURSE_PASSING_STATUS"].apply(lambda s: int((s == "InProgress").sum())),
        "completed": g["FLAG_COMPLETED"].sum(),
        "past_due": g["COMPLIANCE_STATUS"].apply(lambda s: int((s == "NOT COMPLIANT").sum())),
        "mandatory": g["FLAG_COMPLIANCE_SCOPE"].sum(),
    })
    plans = snap.plan_courses.groupby("LMS_COURSE_ID")["LMS_TRAINING_PLAN_ID"].nunique() \
        if not snap.plan_courses.empty else pd.Series(dtype=int)
    out = c.set_index("LMS_COURSE_ID").join(stats).fillna({k: 0 for k in stats.columns})
    out["core_plans"] = plans.reindex(out.index).fillna(0).astype(int)
    out["completion_pct"] = (out["completed"] / out["enrolled"]).where(out["enrolled"] > 0)
    return out.reset_index()


def person_stats(ppl, enr, start=None, end=None):
    """One row per person: assignments, completions, past due, hours (in period)."""
    a = assignments(enr)
    comp = completions(enr, start, end) if end else a[a["FLAG_COMPLETED"] == 1]
    ga, gc = a.groupby("LMS_USER_ID"), comp.groupby("LMS_USER_ID")
    out = ppl.set_index("LMS_USER_ID")[["NAME_FULL", "EMAIL", "JOB_TITLE", "GROUP_TYPE", "PROPERTY_KEY",
                                        "PROPERTY_NAME", "EMPLOYEE_STATUS", "DATETIME_HIRED"]].copy()
    out["assigned"] = ga.size()
    out["open"] = ga["FLAG_COMPLETED"].apply(lambda s: int((s == 0).sum()))
    out["past_due"] = past_due(enr).groupby("LMS_USER_ID").size()
    out["completed"] = gc.size()
    out["hours"] = gc["TRAINING_MINUTES"].sum() / 60
    gm = mandatory(enr).groupby("LMS_USER_ID")["FLAG_COMPLIANT"]
    out["mandatory"] = gm.size()
    out["compliance_pct"] = gm.mean()
    out = out.fillna({"assigned": 0, "open": 0, "past_due": 0, "completed": 0, "hours": 0, "mandatory": 0})
    return out.reset_index()


def location_stats(ppl, enr, start, end, upcoming_days=30):
    """One row per location: headcount, activity in period, past due, upcoming, compliance."""
    heads = associates(ppl).groupby("PROPERTY_KEY").size()
    comp = completions(enr, start, end).groupby("PROPERTY_KEY")
    mand = mandatory(enr).groupby("PROPERTY_KEY")
    upc = upcoming(enr, upcoming_days).groupby("PROPERTY_KEY").size()
    rows = []
    for key, g in ppl.groupby("PROPERTY_KEY"):
        first = g.iloc[0]
        c = comp.get_group(key) if key in comp.groups else None
        m = mand.get_group(key) if key in mand.groups else None
        n_assoc = int(heads.get(key, 0))
        hours = float(c["TRAINING_MINUTES"].sum() / 60) if c is not None else 0.0
        mc = _counts(m) if m is not None else _counts(enr.iloc[0:0])
        rows.append({
            "property_key": int(key), "property_name": first["PROPERTY_NAME"],
            "rm_name": first["RM_NAME"], "rvp_name": first["RVP_NAME"],
            "associates": n_assoc,
            "completions": len(c) if c is not None else 0,
            "hours": hours,
            "hours_per_associate": hours / n_assoc if n_assoc else None,
            "past_due": mc["not_compliant"],
            "upcoming": int(upc.get(key, 0)),
            "pct": mc["pct"],
        })
    rows.sort(key=lambda r: r["property_name"])
    return rows


def filter_options(ppl):
    def opts(col):
        return sorted(v for v in ppl[col].dropna().unique() if v not in ("", "NA"))
    locs = ppl[["PROPERTY_KEY", "PROPERTY_NAME"]].drop_duplicates().sort_values("PROPERTY_NAME")
    return {"property_type": opts("PROPERTY_TYPE_LMS"), "rvp": opts("RVP_NAME"), "rm": opts("RM_NAME"),
            "role": opts("GROUP_TYPE"),
            "property": [(int(k), n) for k, n in locs.itertuples(index=False)]}


def apply_filters(df, property_type=None, rvp=None, rm=None):
    """Kept for the Location Compliance view's existing query parameters."""
    if property_type:
        df = df[df["PROPERTY_TYPE_LMS"] == property_type]
    if rvp:
        df = df[df["RVP_NAME"] == rvp]
    if rm:
        df = df[df["RM_NAME"] == rm]
    return df
