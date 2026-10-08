"""Routes. One blueprint; each tab lives in its own module and registers on `bp`."""

import io
from datetime import datetime

import pandas as pd
from flask import (Blueprint, abort, current_app, g, redirect, render_template, request,
                   send_file, session, url_for)

from .. import metrics
from ..access import resolve, sample_viewers
from ..config import Config

# AppHub-native blueprint: mounted at /peak-academy, serving its own templates
# and static assets. The blueprint NAME stays "lms" so the many url_for('lms.*')
# references across templates and views keep working unchanged.
bp = Blueprint(
    "lms", __name__,
    url_prefix="/peak-academy",
    template_folder="../templates",
    static_folder="../static",
    static_url_path="/static",
)

# Lazily-loaded workspace env for AppHub DB access.
_env = None


def _get_env():
    global _env
    if _env is None:
        from helpers import load_env
        _env = load_env()
    return _env


def _admin_emails():
    """LMS admins = APP_ADMINS rows for App_ID 38, plus the current developer.

    During impersonation is_developer is False and the email is the impersonated
    person, so admin status correctly reflects the viewed identity.
    """
    from helpers import SafeConnection
    emails = set()
    try:
        conn = SafeConnection(_get_env(), "DB_APP_SUPPORT", None, direct=True)
        rows = conn.fetchall("SELECT LOWER(ADMIN_EMAIL) FROM dbo.APP_ADMINS WHERE APP_ID = 38")
        emails = {r[0] for r in rows if r[0]}
    except Exception:
        pass
    if session.get("is_developer"):
        e = (_current_email() or "").lower()
        if e:
            emails.add(e)
    return emails

# Sidebar: (endpoint, label). Endpoints listed in TAB_OF map sub-pages onto their tab.
NAV = [
    ("lms.overview", "Overview"),
    ("lms.locations", "Training Compliance"),
    ("lms.courses", "Course Details"),
    ("lms.core", "CORE Onboarding"),
    ("lms.people", "Associate Training"),
    ("lms.offices", "Office Locations"),
    ("lms.reports", "Reports"),
    ("lms.definitions", "Definitions"),
]
ADMIN_NAV = [("lms.questions", "Open Questions")]  # shown to admins only
TAB_OF = {
    "lms.location": "lms.locations", "lms.course": "lms.courses", "lms.core_plan": "lms.core",
    "lms.person": "lms.people", "lms.report": "lms.reports",
}


# --------------------------------------------------------------------------- request context

def store():
    return current_app.extensions["lms_store"]


def _current_email():
    """Effective AppHub identity (impersonated user when View-As is active)."""
    return (session.get("user", {}) or {}).get("email", "") or ""


@bp.before_request
def _load_context():
    # AppHub login gate — mirrors auth.login_required (incl. dev bypass) without
    # decorating each route.
    if not session.get("user"):
        from auth import _DEV_BYPASS, _DEV_USER, _dev_user_modules
        if _DEV_BYPASS:
            session["user"] = _DEV_USER
            session["is_developer"] = True
            session["security_level"] = 100
            session["user_modules"] = _dev_user_modules()
        else:
            return redirect(url_for("auth.login"))
    g.snap = store().get()
    g.viewer = resolve(_current_email(), g.snap.users, _admin_emails())


@bp.context_processor
def _inject():
    from config import APP_VERSION
    from nav import build_nav_modules
    return {
        "viewer": g.viewer,
        "snap": g.snap,
        "dev_mode": False,  # AppHub supplies View-As; the LMS dev switcher is off.
        "nav": NAV + (ADMIN_NAV if g.viewer.is_admin else []),
        "active_tab": TAB_OF.get(request.endpoint, request.endpoint),
        "view_as_options": [],
        # ── AppHub shell.html context ──────────────────────────────────────
        "modules": build_nav_modules(),
        "active_module": "peak_academy_lms",
        "user": session.get("user", {}),
        "is_developer": session.get("is_developer", False),
        "is_dev_mode": session.get("is_dev_mode", False),
        "is_impersonating": session.get("is_impersonating", False),
        "impersonating_user": session.get("impersonating_user", None),
        "version": APP_VERSION,
    }


# --------------------------------------------------------------------------- shared helpers

def visible_people(f=None):
    return metrics.people(g.snap, g.viewer.allowed_keys, f)


def all_options():
    return metrics.filter_options(visible_people())


def period_from_args(default="all"):
    """The completions / training-hours window. Compliance, past due and upcoming ignore it."""
    preset = request.args.get("period") or default
    start, end = metrics.period_bounds(preset, g.snap.as_of or datetime.now().date())
    return preset, start, end


def require_admin():
    if not g.viewer.is_admin:
        abort(403)


def record(row):
    """A DataFrame row as a dict with NaN -> None (NaN is truthy in Jinja)."""
    return {k: (None if not isinstance(v, (str, list, dict)) and pd.isna(v) else v) for k, v in row.items()}


def records(df):
    return [record(r) for r in df.to_dict("records")]


def export(rows, columns, stem):
    """rows: list of dicts; columns: [(key, header, ...)]. Honours ?format=csv|xlsx."""
    keys = [c[0] for c in columns]
    df = pd.DataFrame([{k: _cell(r.get(k)) for k in keys} for r in rows], columns=keys)
    df = df.rename(columns={c[0]: c[1] for c in columns})
    stamp = datetime.now().strftime("%Y%m%d")
    if request.args.get("format") == "csv":
        buf = io.BytesIO(df.to_csv(index=False).encode("utf-8-sig"))
        return send_file(buf, mimetype="text/csv", as_attachment=True, download_name=f"{stem}_{stamp}.csv")
    buf = io.BytesIO()
    df.to_excel(buf, index=False, sheet_name=stem[:31])
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=f"{stem}_{stamp}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def _cell(v):
    """Neutralise text Excel would run as a formula (=, +, -, @ at the start)."""
    return "'" + v if isinstance(v, str) and v[:1] in ("=", "+", "-", "@") else v


def wants_export():
    return request.args.get("format") in ("csv", "xlsx")


# --------------------------------------------------------------------------- shared routes

@bp.route("/")
def index():
    return redirect(url_for("lms.overview"))


@bp.route("/dev/view-as", methods=["POST"])
def view_as():
    # The LMS dev switcher is never used in AppHub (AppHub supplies View-As).
    abort(404)


@bp.route("/admin/refresh", methods=["POST"])
def refresh():
    require_admin()
    store().refresh()
    return redirect(request.referrer or url_for("lms.overview"))


@bp.app_errorhandler(403)
def forbidden(_):
    return render_template("message.html", title="Not available",
                           body="You don't have access to that page or location."), 403


# --------------------------------------------------------------------------- jinja filters

def _missing(v):
    return v is None or (not isinstance(v, (str, list, dict)) and pd.isna(v))


def _pct(v):
    return "–" if _missing(v) else f"{v:.0%}"


def _date(v):
    if _missing(v):
        return ""
    t = pd.Timestamp(v)
    return f"{t.month}/{t.day}/{t.year}"


def _num(v):
    return "" if _missing(v) else f"{int(round(v)):,}"


def _hours(v):
    return "" if _missing(v) else f"{v:,.1f}"


def _title(v):
    return "" if _missing(v) else str(v).title()


def _band(v):
    """Colour band for a compliance ratio."""
    if _missing(v):
        return "none"
    return "good" if v >= 0.9 else "warn" if v >= 0.75 else "bad"


def _progress(v):
    return {"NotStarted": "Not started", "InProgress": "In progress"}.get(v, v or "")


FILTERS = {"pct": _pct, "date": _date, "num": _num, "hours": _hours, "titlecase": _title,
           "band": _band, "progress": _progress, "missing": _missing}


from . import about, compliance, core, courses, locations, overview, people, questions, reports  # noqa: E402,F401
