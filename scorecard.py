"""Leadership & Maintenance Scorecard module -- quarterly RM bonus scoring.

Data source : WH_PROD2 (LS_TIMESHEET, LS_TRAINING, LS_PREPAID_VISA, LS_RISK_ASSESSMENT,
              LS_IIPP, LS_LEASE_FILE_AUDIT, LEO_COMPLIANCE_EXPORT_FACT,
              REPUTATION_COM_SUMMARY_FACT, LS_RM_QUARTERLY_INSPECTION_SCORES_FACT,
              WORK_ORDER_REQUESTS, INCOME_STATEMENT_BY_GL)
Identity    : DB_APP_SUPPORT.dbo.Emp_Core (NOT EMPLOYEE_F -- EMPLOYEE_F is being retired)
APP_ID      : 36
"""
from flask import Blueprint, render_template, session, jsonify, request, abort, send_file
import json
import os
import re
from auth import login_required
from nav import build_nav_modules
from helpers import load_env, SafeConnection, _get_fabric_api_token
import datetime

scorecard_bp = Blueprint("scorecard", __name__, url_prefix="/scorecard")

APP_ID = 36

# Column order/shape returned by /api/data -- matches SCORECARD_CORE's shape,
# not the full 74-column DDL (locks/audit metadata aren't needed by the
# read-only Phase 2 grid; Phase 3 subjective-entry adds its own save endpoint).
_GRID_COLUMNS = [
    "PROPERTY_KEY", "ENTITY_NUMBER", "PROPERTY_NAME", "QUARTER_YEAR",
    "PROPERTY_TYPE",
    "RM_EMAIL", "RM_NAME",
    "RMSCORE",
    "TC", "TR", "PCARD", "RA", "IIPP", "LFA", "PMLEO", "REP", "WO",
    "PRERM", "LDRTOTAL",
    "MSLEO", "CURB", "PUBLICAREAS", "MAINT", "LOGS", "MSWO",
    "SURVEYS", "NOI", "MSTOTAL",
    "COMPLETE_CY", "COMPLETE_TARGET", "COMPLETE_VS_TARGET",
    "NEW_CY", "NEW_TARGET", "NEW_VS_TARGET",
    "RENEWAL_CY", "RENEWAL_TARGET", "RENEWAL_VS_TARGET",
    "NOTES", "NOTE_BY", "NOTE_AT",
]

# Every measure the override slideout can edit -- key must match a real
# SCORECARD_CORE column that also has a <key>_LOCKED companion bit. "blurb"
# mirrors the plain-language source/logic write-up already reviewed with
# stakeholders (scorecard_stakeholder_confirmation_checklist.html) so the
# same explanation doesn't have to be maintained in two places from scratch.
_MEASURE_DEFS = [
    {"key": "TC", "label": "Timecard Approval", "group": "leadership", "type": "bool",
     "blurb": "Paycom timecards approved by a Supervisor, checked against the NY/Non-NY due-date calendars (+10h10m buffer, +2h more for West Coast properties). Pass if ~100% approved on time; defaults to PASS if no timecard data exists for the quarter."},
    {"key": "TR", "label": "Training Compliance", "group": "leadership", "type": "bool",
     "blurb": "Average of the last recorded monthly compliance % (Grace Hill, soon Peak Academy) across the quarter's 3 months. Pass threshold is >=94%."},
    {"key": "PCARD", "label": "PPV / P-Card", "group": "leadership", "type": "bool",
     "blurb": "CONFIRMED working as designed (2026-09-22 stakeholder meeting): fails if the property has ANY Prepaid Visa reconciliation transaction in the quarter; zero transactions = pass by default."},
    {"key": "RA", "label": "Risk Assessment", "group": "leadership", "type": "bool",
     "blurb": "Compliance import completion. FLAGGED: production hardcodes this to only ever evaluate Q4 -- likely a bug, pending stakeholder confirmation."},
    {"key": "IIPP", "label": "IIPP", "group": "leadership", "type": "bool",
     "blurb": "CONFIRMED (2026-09-22): any monthly snapshot in the quarter showing incomplete fails the whole quarter -- not a simple single-flag passthrough."},
    {"key": "LFA", "label": "Lease File Audit", "group": "leadership", "type": "bool",
     "blurb": "CONFIRMED (2026-09-22): any monthly snapshot in the quarter showing incomplete fails the whole quarter -- not a simple single-flag passthrough."},
    {"key": "PMLEO", "label": "PM LEO Compliance", "group": "leadership", "type": "bool",
     "blurb": "CONFIRMED (2026-09-22): any monthly snapshot in the quarter showing incomplete fails the whole quarter -- not a simple single-flag passthrough."},
    {"key": "REP", "label": "Reputation Score", "group": "leadership", "type": "bool",
     "blurb": "Compares this quarter's closing-Friday score vs. the prior quarter's. Pass if improvement is >1%; defaults to PASS if either score is missing."},
    {"key": "WO", "label": "Work Orders (PM)", "group": "leadership", "type": "bool",
     "blurb": "Average of each month's average open-day count for completed work orders across the quarter. Pass threshold is <=1 day."},
    {"key": "RMSCORE", "label": "RM Score (0-5)", "group": "leadership", "type": "num5",
     "blurb": "Regional Manager's subjective 0-5 assessment of the Property Manager's leadership this quarter. Manually entered, not calculated."},
    {"key": "MSLEO", "label": "MS LEO Compliance", "group": "maintenance", "type": "bool",
     "blurb": "CONFIRMED (2026-09-22): any monthly snapshot in the quarter showing incomplete fails the whole quarter -- not a simple single-flag passthrough."},
    {"key": "CURB", "label": "Curb Appeal", "group": "maintenance", "type": "bool",
     "blurb": "RM Quarterly Inspection score for this section. When a property has more than one inspection in the quarter, the best score of any inspection is used. Pass threshold is >=85 points."},
    {"key": "PUBLICAREAS", "label": "Public Areas", "group": "maintenance", "type": "bool",
     "blurb": "RM Quarterly Inspection score for this section. When a property has more than one inspection in the quarter, the best score of any inspection is used. Pass threshold is >=85 points."},
    {"key": "MAINT", "label": "Maintenance", "group": "maintenance", "type": "bool",
     "blurb": "RM Quarterly Inspection score for this section. When a property has more than one inspection in the quarter, the best score of any inspection is used. Pass threshold is >=85 points."},
    {"key": "LOGS", "label": "Safety Logs & Binders", "group": "maintenance", "type": "bool",
     "blurb": "RM Quarterly Inspection score for this section. When a property has more than one inspection in the quarter, the best score of any inspection is used. Pass threshold is >=85 points."},
    {"key": "MSWO", "label": "Work Orders (Maintenance)", "group": "maintenance", "type": "bool",
     "blurb": "Same work-order turnaround figure as WO, applied to the Maintenance Supervisor's score. Pass threshold is <=1 day."},
    {"key": "SURVEYS", "label": "Surveys", "group": "maintenance", "type": "bool01",
     "blurb": "Regional Manager's subjective 0/1 confirmation that resident surveys were completed this quarter. Manually entered, not calculated."},
    {"key": "NOI", "label": "Controllable NOI", "group": "maintenance", "type": "bool01",
     "blurb": "CONFIRMED (2026-09-22): this is manually entered/overridden here -- there is no automated file feed for NOI today. Use this slideout to set it directly."},
]
_MEASURE_KEYS = [m["key"] for m in _MEASURE_DEFS]
_MEASURE_DEFS_BY_KEY = {m["key"]: m for m in _MEASURE_DEFS}
_OBJECTIVE_KEYS = ["TC", "TR", "PCARD", "RA", "IIPP", "LFA", "PMLEO", "REP", "WO"]
_MAINT_TOTAL_KEYS = ["MSLEO", "CURB", "PUBLICAREAS", "MAINT", "LOGS", "MSWO", "NOI", "SURVEYS"]
# <key>_LOCKED / _LOCKED_BY / _REASON companion columns -- appended to the
# grid query so the main table can outline overridden cells and show a
# who/why tooltip without a separate per-property fetch.
_LOCK_COLUMNS = [f"{k}_LOCKED" for k in _MEASURE_KEYS]
_LOCK_BY_COLUMNS = [f"{k}_LOCKED_BY" for k in _MEASURE_KEYS]
_REASON_COLUMNS = [f"{k}_REASON" for k in _MEASURE_KEYS]

_env = None


def _get_env():
    global _env
    if _env is None:
        _env = load_env()
    return _env


def _require_access():
    """Check that the current user has access to the Leadership Scorecard (app_id=36)."""
    if session.get("is_developer"):
        return None
    user_modules = session.get("user_modules", [])
    for m in user_modules:
        if m["id"] == APP_ID:
            return None
    return jsonify({"error": "unauthorized"}), 403


def _is_real_admin():
    """Admin check for Leadership Scorecard. Three ways in:
      1. is_developer flag (set at login from MODULE_AUDIENCE GRANT_TYPE='developer')
      2. user_modules entry for this app with access=='admin'  <-- Audience Manager
         (MODULE_AUDIENCE ACCESS_LEVEL='admin', via any grant type)
      3. legacy dbo.APP_ADMINS row for this APP_ID + email

    Ignores any active "View as ..." simulation so we always know whether
    the underlying user CAN toggle view-as (needed by the view-as management
    endpoints themselves)."""
    if session.get("is_developer"):
        return True
    for m in session.get("user_modules", []):
        if m.get("id") == APP_ID and (m.get("access") or "").lower() == "admin":
            return True
    user = session.get("user", {})
    email = user.get("email", "").lower()
    if not email:
        return False
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        return conn.scalar(
            "SELECT COUNT(*) FROM dbo.APP_ADMINS WHERE APP_ID = ? AND LOWER(ADMIN_EMAIL) = ?",
            [APP_ID, email]
        ) > 0
    finally:
        conn.close()


def _is_admin():
    """Check if current user is an admin for Leadership Scorecard (APP_ID=36).
    Same dbo.APP_ADMINS-backed pattern used by every other AppHub module
    (cultivate.py/fasttrack.py/etc.) -- admins see every property; everyone
    else is scoped to their own RM_EMAIL via SCORECARD_CORE.

    IF the admin has activated any "View as..." simulation (RM/PM/RVP)
    returns False so all scoping/gating treats them as that role. Use
    _is_real_admin() when you need the underlying flag (e.g. to toggle out
    of the simulation)."""
    if (session.get("sc_view_as_email")
            or session.get("sc_view_as_pm_property_key")
            or session.get("sc_view_as_rvp_email")):
        return False
    return _is_real_admin()


def _effective_rm_email():
    """The email used for RM-scoping in every read/write endpoint.
    Returns the "view as" email if a real admin is currently simulating an
    RM, else the signed-in user's own email."""
    if session.get("sc_view_as_email") and _is_real_admin():
        return session["sc_view_as_email"].lower()
    return (session.get("user", {}).get("email") or "").lower()


def _pm_property_key():
    """Return the PROPERTY_KEY a Property Manager is scoped to, or None if
    the current user is not a PM. Cached in the session after first lookup.

    Precedence:
    1. Real admin currently simulating a PM (sc_view_as_pm_property_key) -- returns that key.
    2. Real admin not simulating -- returns None (admins are not PMs).
    3. Non-admin -- looks up Emp_Core.TITLE_GROUP for 'Property Manager' + PROPERTY_KEY."""
    if _is_real_admin():
        pm_sim = session.get("sc_view_as_pm_property_key")
        return int(pm_sim) if pm_sim else None
    if "sc_pm_property_key" in session:
        val = session["sc_pm_property_key"]
        return val if val else None
    user = session.get("user", {})
    email = (user.get("email") or "").lower()
    if not email:
        session["sc_pm_property_key"] = 0
        return None
    profile = None
    try:
        profile = get_rm_profile(email)
    except Exception:
        profile = None
    if not profile:
        session["sc_pm_property_key"] = 0
        return None
    tg = (profile.get("title_group") or "").lower()
    prop_key = profile.get("property_key")
    if "property manager" in tg and prop_key:
        session["sc_pm_property_key"] = int(prop_key)
        return int(prop_key)
    session["sc_pm_property_key"] = 0
    return None


def _is_pm():
    """True if the current user is a Property Manager (single-property, read-only)."""
    return _pm_property_key() is not None


# ─── RVP scoping ───────────────────────────────────────────────────────
# Regional Vice Presidents see every property whose PROPERTY_0.RVP_EMAIL
# matches theirs -- effectively the union of their RMs' portfolios. They
# have the same write posture as RMs (override, patch, notes) within that
# region. Detected via Emp_Core.TITLE_GROUP = 'REGIONAL VICE PRESIDENT'.
#
# _RVP_ALL_PROPERTIES_EMAILS: RVP-titled leaders who legitimately see the
# entire portfolio (e.g. Sr VP Ops). They still run in RVP mode -- no admin
# badges/tools -- but the scope filter degrades to "all reportable
# properties" instead of the RVP_EMAIL equality check.
_RVP_ALL_PROPERTIES_EMAILS = {"melmore@peakmade.com"}


def _is_rvp():
    """True if the current user is a Regional Vice President.
    Real admins simulating "View as RVP" also count. Cached per session."""
    if _is_real_admin():
        return bool(session.get("sc_view_as_rvp_email"))
    if "sc_is_rvp" in session:
        return bool(session["sc_is_rvp"])
    user = session.get("user", {})
    email = (user.get("email") or "").lower()
    if not email:
        session["sc_is_rvp"] = False
        return False
    try:
        profile = get_rm_profile(email)
    except Exception:
        profile = None
    is_rvp = bool(profile and (profile.get("title_group") or "").upper() == "REGIONAL VICE PRESIDENT")
    session["sc_is_rvp"] = is_rvp
    return is_rvp


def _effective_rvp_email():
    """Email used for RVP-scoping in every read/write endpoint. Honors admin
    'View as RVP' simulation."""
    if _is_real_admin() and session.get("sc_view_as_rvp_email"):
        return session["sc_view_as_rvp_email"].lower()
    return (session.get("user", {}).get("email") or "").lower()


def _rvp_sees_all():
    """True if the current RVP has an all-properties override (Sr VP Ops etc.).
    They still operate in RVP mode -- no admin surfaces -- but scope is
    unfiltered so they see every reportable property."""
    return _is_rvp() and _effective_rvp_email() in _RVP_ALL_PROPERTIES_EMAILS


def _scope_clause(alias="sc"):
    """Return (where_sql, params) that scopes a SELECT to the current user's
    role. The RM and RVP branches assume the caller has already joined
    dbo.PROPERTY_0 p ON p.PROPERTY_KEY = <alias>.PROPERTY_KEY -- adds an
    empty '1=1' filter otherwise, so admin/pm-only queries stay JOIN-free.
      admin, pm, rvp-all -> no filter
      pm                 -> <alias>.PROPERTY_KEY = ?
      rvp                -> LOWER(p.RVP_EMAIL) = ?
      rm (default)       -> LOWER(COALESCE(p.RM_EMAIL, <alias>.RM_EMAIL)) = ?
    """
    if _is_admin():
        return "1=1", []
    pm_key = _pm_property_key()
    if pm_key:
        return f"{alias}.PROPERTY_KEY = ?", [pm_key]
    if _is_rvp():
        if _rvp_sees_all():
            return "1=1", []
        return "LOWER(p.RVP_EMAIL) = ?", [_effective_rvp_email()]
    return f"LOWER(COALESCE(p.RM_EMAIL, {alias}.RM_EMAIL)) = ?", [_effective_rm_email()]


def _scope_update_where():
    """Return (where_sql, params) for an UPDATE against dbo.SCORECARD_CORE
    that has no PROPERTY_0 join. RVP mode uses a subquery on PROPERTY_0 to
    verify the property belongs to the RVP's region. Callers should have
    already verified ownership via _scoped_property_row -- this is
    defense-in-depth."""
    if _is_admin():
        return "", []
    pm_key = _pm_property_key()
    if pm_key:
        return " AND PROPERTY_KEY = ?", [pm_key]
    if _is_rvp():
        if _rvp_sees_all():
            return "", []
        return (" AND EXISTS (SELECT 1 FROM dbo.PROPERTY_0 p "
                "WHERE p.PROPERTY_KEY = dbo.SCORECARD_CORE.PROPERTY_KEY "
                "AND LOWER(p.RVP_EMAIL) = ?)"), [_effective_rvp_email()]
    return " AND LOWER(RM_EMAIL) = ?", [_effective_rm_email()]



def get_rm_profile(email):
    """Resolve the signed-in user's RM identity + portfolio via Emp_Core.

    Deliberately uses DB_APP_SUPPORT.dbo.Emp_Core instead of WH_STAGING.dbo.EMPLOYEE_F --
    EMPLOYEE_F is being retired shortly. Emp_Core carries the same identity fields
    (EMAIL, TITLE_GROUP, PROPERTY_KEY, PROPERTY_GROUP, RM_REGION, SUPERVISOR_NAME)
    plus FLAG_CURRENT to scope to the active record.
    """
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        rows = conn.fetchall("""
            SELECT TOP 1 EMPLOYEE_CODE, NAME_FULL, EMAIL, TITLE, TITLE_GROUP,
                   PROPERTY_KEY, PROPERTY_GROUP, RM_REGION, RVP_REGION,
                   SUPERVISOR_NAME, FLAG_ACTIVE
            FROM dbo.Emp_Core
            WHERE LOWER(EMAIL) = ? AND FLAG_CURRENT = 1
        """, (email.lower(),))
        if not rows:
            return None
        r = rows[0]
        return {
            "employee_code": r[0],
            "name": r[1],
            "email": r[2],
            "title": r[3],
            "title_group": r[4] or "",
            "property_key": r[5],
            "property_group": r[6],
            "rm_region": r[7],
            "rvp_region": r[8],
            "supervisor_name": r[9],
            "active": r[10],
        }
    finally:
        conn.close()


def _ctx(**kwargs):
    user = session.get("user", {})
    email = user.get("email", "")
    is_dev = session.get("is_developer", False)
    rm_profile = None
    if email:
        try:
            rm_profile = get_rm_profile(email)
        except Exception:
            rm_profile = None
    view_as_email = session.get("sc_view_as_email") if _is_real_admin() else None
    view_as_pm_key = session.get("sc_view_as_pm_property_key") if _is_real_admin() else None
    view_as_rvp_email = session.get("sc_view_as_rvp_email") if _is_real_admin() else None
    view_as_pm_label = None
    if view_as_pm_key:
        try:
            env = _get_env()
            conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
            try:
                name = conn.scalar(
                    "SELECT TOP 1 PROPERTY_NAME FROM dbo.SCORECARD_CORE WHERE PROPERTY_KEY = ? AND FLAG_CURRENT = 1",
                    [int(view_as_pm_key)],
                )
                view_as_pm_label = name or f"Property {view_as_pm_key}"
            finally:
                conn.close()
        except Exception:
            view_as_pm_label = f"Property {view_as_pm_key}"
    pm_prop_key = _pm_property_key()
    is_rvp = _is_rvp()
    ctx = dict(
        modules=build_nav_modules(),
        active_module="leadership_scorecard",
        user=user,
        is_developer=is_dev,
        is_dev_mode=session.get("is_dev_mode", False),
        is_impersonating=session.get("is_impersonating", False),
        impersonating_user=session.get("impersonating_user", None),
        rm_profile=rm_profile,
        is_admin=_is_admin(),
        is_real_admin=_is_real_admin(),
        view_as_email=view_as_email,
        view_as_pm_property_key=view_as_pm_key,
        view_as_pm_label=view_as_pm_label,
        view_as_rvp_email=view_as_rvp_email,
        is_pm=pm_prop_key is not None,
        pm_property_key=pm_prop_key,
        is_rvp=is_rvp,
        rvp_email=_effective_rvp_email() if is_rvp else None,
        rvp_sees_all=_rvp_sees_all(),
        measure_defs=_MEASURE_DEFS,
    )
    ctx.update(kwargs)
    return ctx


@scorecard_bp.route("/")
@login_required
def index():
    """Render the Leadership Scorecard page within the shell framework."""
    check = _require_access()
    if check:
        return check
    return render_template("scorecard.html", **_ctx())


# LeadershipScorecard/ is the sibling folder to APPHUB_4/ (see file layout in
# apphub4.md memory) -- the diagrams live there, not under APPHUB_4/static/.
_DIAGRAM_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "LeadershipScorecard"))
_DIAGRAM_FILES = {
    "dataflow": "scorecard_dataflow_diagram.html",
    "table_manager": "scorecard_table_manager_diagram.html",
}


@scorecard_bp.route("/admin/diagram/<diagram_name>")
@login_required
def admin_diagram(diagram_name):
    """Serve the standalone data-flow / table-manager diagrams from the
    sibling LeadershipScorecard/ folder as-is (they're self-contained dark-
    theme HTML with their own SVG/JS). Admin-gated -- these are the
    interactive architecture views a stakeholder or on-call engineer would
    want to open to understand what the pipeline does."""
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin only"}), 403
    filename = _DIAGRAM_FILES.get(diagram_name)
    if filename is None:
        abort(404)
    path = os.path.join(_DIAGRAM_DIR, filename)
    if not os.path.exists(path):
        abort(404)
    return send_file(path, mimetype="text/html")


# Registry of every table feeding or produced by the Scorecard pipeline.
# Mirrors edm.py's EMP_PIPELINE_TABLES pattern -- browse-only, TOP 3000, table
# names come from this whitelist so the endpoint can't be used to reach
# arbitrary tables. Admin-gated.
_TABLE_REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "scorecard_tables.json")

def _load_scorecard_tables():
    if not os.path.exists(_TABLE_REGISTRY_PATH):
        return {}
    try:
        with open(_TABLE_REGISTRY_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


@scorecard_bp.route("/admin/tables")
@login_required
def admin_tables_page():
    """Admin-only Table Manager page -- browse every table feeding or produced
    by the Scorecard pipeline. Rendered inside the shell (unlike the raw
    dark-theme diagrams which are served as standalone HTML)."""
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin only"}), 403
    return render_template("scorecard_table_manager.html", **_ctx())


@scorecard_bp.route("/api/admin/tables")
@login_required
def api_admin_tables():
    """Return the whole table registry -- powers the Table Manager left-nav."""
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin only"}), 403
    return jsonify(_load_scorecard_tables())


@scorecard_bp.route("/admin/runs")
@login_required
def admin_runs_page():
    """Admin-only Pipeline Runs viewer -- lists recent pipeline executions
    and per-step outcomes so admins can triage without leaving AppHub."""
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin only"}), 403
    return render_template("scorecard_pipeline_runs.html", **_ctx())


# ── QA Sign-Off admin page + shared-state API ────────────────────────────
# In-app version of the standalone LEADERSHIP_SCORECARD_QA_SIGNOFF.html.
# All state lives in dbo.SCORECARD_QA_STATE / SCORECARD_QA_META so multiple
# testers see and update the same checklist. Any admin can edit; per-row
# LAST_UPDATED_BY + LAST_UPDATED_AT provide an audit trail.

@scorecard_bp.route("/admin/qa")
@login_required
def admin_qa_page():
    """Shared QA Sign-Off page -- any Scorecard user can participate as a tester.
    Reset-all remains admin-only (see api_admin_qa_reset)."""
    check = _require_access()
    if check:
        return check
    return render_template("scorecard_qa_signoff.html", **_ctx())


@scorecard_bp.route("/api/admin/qa/state")
@login_required
def api_admin_qa_state():
    """Return the full current checklist state: all row entries + meta singleton."""
    check = _require_access()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        rows = conn.fetchall("""
            SELECT SCENARIO_KEY, CHECKED, STATUS, NOTES,
                   LAST_UPDATED_BY, LAST_UPDATED_AT
            FROM dbo.SCORECARD_QA_STATE
        """)
        state = {r[0]: {"checked": bool(r[1]), "status": r[2], "notes": r[3],
                        "last_updated_by": r[4],
                        "last_updated_at": r[5].isoformat() if r[5] else None}
                 for r in rows}
        meta_row = conn.fetchall("""
            SELECT TESTER, TEST_DATE, ENV, BROWSER, ROLE_TESTED,
                   SIGNOFF_TESTER, SIGNOFF_APPROVER, DECISION, BLOCKERS,
                   LAST_UPDATED_BY, LAST_UPDATED_AT
            FROM dbo.SCORECARD_QA_META WHERE META_ID = 1
        """)
        m = meta_row[0] if meta_row else (None,) * 11
        meta = {
            "tester": m[0], "test_date": m[1].isoformat() if m[1] else None,
            "env": m[2], "browser": m[3], "role_tested": m[4],
            "signoff_tester": m[5], "signoff_approver": m[6],
            "decision": m[7], "blockers": m[8],
            "last_updated_by": m[9],
            "last_updated_at": m[10].isoformat() if m[10] else None,
        }
        return jsonify({"state": state, "meta": meta})
    finally:
        conn.close()


@scorecard_bp.route("/api/admin/qa/row/<scenario_key>", methods=["PUT"])
@login_required
def api_admin_qa_row(scenario_key):
    """Upsert one scenario's checked / status / notes. Body: {checked, status, notes}."""
    check = _require_access()
    if check:
        return check
    if len(scenario_key) > 50 or not scenario_key.replace("_", "").isalnum():
        return jsonify({"error": "invalid scenario_key"}), 400
    payload = request.get_json(silent=True) or {}
    checked = 1 if payload.get("checked") else 0
    status = payload.get("status") or None
    if status not in (None, "pass", "fail", "block"):
        return jsonify({"error": "invalid status"}), 400
    notes = (payload.get("notes") or "")[:2000] or None
    user = session.get("user", {})
    by = user.get("email") or user.get("name") or "unknown"
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute("""
            MERGE dbo.SCORECARD_QA_STATE AS tgt
            USING (SELECT ? AS SCENARIO_KEY, ? AS CHECKED, ? AS STATUS, ? AS NOTES, ? AS BY_) AS src
              ON tgt.SCENARIO_KEY = src.SCENARIO_KEY
            WHEN MATCHED THEN UPDATE SET
                CHECKED = src.CHECKED, STATUS = src.STATUS, NOTES = src.NOTES,
                LAST_UPDATED_BY = src.BY_, LAST_UPDATED_AT = SYSUTCDATETIME()
            WHEN NOT MATCHED THEN INSERT
                (SCENARIO_KEY, CHECKED, STATUS, NOTES, LAST_UPDATED_BY, LAST_UPDATED_AT)
                VALUES (src.SCENARIO_KEY, src.CHECKED, src.STATUS, src.NOTES, src.BY_, SYSUTCDATETIME());
        """, (scenario_key, checked, status, notes, by))
        conn.commit()
        return jsonify({"ok": True, "last_updated_by": by})
    finally:
        conn.close()


@scorecard_bp.route("/api/admin/qa/meta", methods=["PUT"])
@login_required
def api_admin_qa_meta():
    """Update the singleton meta row. Any Scorecard user can edit any field
    (testers collaborate on tester/date/env/browser/decision/blockers)."""
    check = _require_access()
    if check:
        return check
    payload = request.get_json(silent=True) or {}
    allowed = ["TESTER", "TEST_DATE", "ENV", "BROWSER", "ROLE_TESTED",
               "SIGNOFF_TESTER", "SIGNOFF_APPROVER", "DECISION", "BLOCKERS"]
    updates = {k.upper(): payload.get(k.lower()) for k in allowed if k.lower() in payload}
    if not updates:
        return jsonify({"error": "no valid fields provided"}), 400
    user = session.get("user", {})
    by = user.get("email") or user.get("name") or "unknown"
    set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
    params = list(updates.values()) + [by]
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute(
            f"UPDATE dbo.SCORECARD_QA_META SET {set_clause}, LAST_UPDATED_BY = ?, LAST_UPDATED_AT = SYSUTCDATETIME() WHERE META_ID = 1",
            params)
        conn.commit()
        return jsonify({"ok": True, "last_updated_by": by})
    finally:
        conn.close()


@scorecard_bp.route("/api/admin/qa/reset", methods=["POST"])
@login_required
def api_admin_qa_reset():
    """Wipe all row state (does NOT touch meta). Requires admin. Meant for
    starting a fresh QA pass after a big code change."""
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin only"}), 403
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute("DELETE FROM dbo.SCORECARD_QA_STATE")
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@scorecard_bp.route("/api/admin/runs")
@login_required
def api_admin_runs():
    """Return summary of last 50 pipeline runs (one row per PIPELINE_RUN_ID)."""
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin only"}), 403
    env = _get_env()
    conn = SafeConnection(env, "DB_BI_SUPPORT", None, direct=True)
    try:
        rows = conn.fetchall("""
            SELECT TOP 50
                PIPELINE_RUN_ID,
                COUNT(*) AS STEPS,
                SUM(CASE WHEN STATUS = 'COMPLETE' THEN 1 ELSE 0 END) AS N_COMPLETE,
                SUM(CASE WHEN STATUS = 'FAILED' THEN 1 ELSE 0 END) AS N_FAILED,
                SUM(CASE WHEN STATUS = 'SKIPPED' THEN 1 ELSE 0 END) AS N_SKIPPED,
                MIN(RUN_TIMESTAMP_START_UTC) AS RUN_START_UTC,
                MAX(RUN_TIMESTAMP_END_UTC) AS RUN_END_UTC,
                SUM(DURATION_SEC) AS TOTAL_DURATION_SEC,
                SUM(ROWS_AFFECTED) AS TOTAL_ROWS
            FROM control.SCORECARD_PIPELINE_RUN_LOG
            GROUP BY PIPELINE_RUN_ID
            ORDER BY MAX(RUN_TIMESTAMP_END_UTC) DESC
        """)
        result = []
        for r in rows:
            overall = "COMPLETE"
            if r[3] and r[3] > 0:
                overall = "FAILED"
            elif r[4] and r[4] > 0 and r[2] < r[1]:
                overall = "PARTIAL"
            result.append({
                "run_id": r[0],
                "steps": r[1],
                "n_complete": r[2],
                "n_failed": r[3] or 0,
                "n_skipped": r[4] or 0,
                "run_start_utc": r[5].isoformat() if r[5] else None,
                "run_end_utc": r[6].isoformat() if r[6] else None,
                "total_duration_sec": float(r[7]) if r[7] is not None else None,
                "total_rows": int(r[8]) if r[8] is not None else 0,
                "overall_status": overall,
            })
        return jsonify({"runs": result})
    finally:
        conn.close()


@scorecard_bp.route("/api/admin/runs/<run_id>")
@login_required
def api_admin_run_detail(run_id):
    """Return per-step detail for a single PIPELINE_RUN_ID."""
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin only"}), 403
    if not isinstance(run_id, str) or not (1 <= len(run_id) <= 100):
        return jsonify({"error": "invalid run_id"}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_BI_SUPPORT", None, direct=True)
    try:
        rows = conn.fetchall("""
            SELECT STEP_ORDER, STEP_GROUP, STEP_NAME, STATUS,
                   RUN_TIMESTAMP_START_UTC, RUN_TIMESTAMP_END_UTC,
                   DURATION_SEC, ROWS_AFFECTED, ERROR_MSG
            FROM control.SCORECARD_PIPELINE_RUN_LOG
            WHERE PIPELINE_RUN_ID = ?
            ORDER BY STEP_ORDER, RUN_TIMESTAMP_START_UTC
        """, (run_id,))
        if not rows:
            return jsonify({"error": "run not found"}), 404
        steps = []
        for r in rows:
            steps.append({
                "step_order": r[0],
                "step_group": r[1],
                "step_name": r[2],
                "status": r[3],
                "start_utc": r[4].isoformat() if r[4] else None,
                "end_utc": r[5].isoformat() if r[5] else None,
                "duration_sec": float(r[6]) if r[6] is not None else None,
                "rows_affected": int(r[7]) if r[7] is not None else 0,
                "error_msg": r[8],
            })
        return jsonify({"run_id": run_id, "steps": steps})
    finally:
        conn.close()


# Scorecard pipeline notebook lookup — display name in the ETL workspace.
_SCORECARD_ETL_WORKSPACE_ID = "a28164c3-c392-4848-83d4-b4a26f4bdef3"
_SCORECARD_NOTEBOOK_NAME = "NB_LEADERSHIP_SCORECARD_UPDATE"
_scorecard_notebook_id_cache = {"id": None}


def _resolve_scorecard_notebook_id(env):
    """Look up NB_LEADERSHIP_SCORECARD_UPDATE's item id in the ETL workspace, cached."""
    if _scorecard_notebook_id_cache["id"]:
        return _scorecard_notebook_id_cache["id"]
    import requests as _requests
    token = _get_fabric_api_token(env)
    r = _requests.get(
        f"https://api.fabric.microsoft.com/v1/workspaces/{_SCORECARD_ETL_WORKSPACE_ID}/items?type=Notebook",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Fabric items list failed: HTTP {r.status_code} {r.text[:200]}")
    for nb in r.json().get("value", []):
        if nb.get("displayName") == _SCORECARD_NOTEBOOK_NAME:
            _scorecard_notebook_id_cache["id"] = nb["id"]
            return nb["id"]
    raise RuntimeError(f"Notebook {_SCORECARD_NOTEBOOK_NAME!r} not found in workspace {_SCORECARD_ETL_WORKSPACE_ID}")


@scorecard_bp.route("/api/admin/runs/trigger", methods=["POST"])
@login_required
def api_admin_run_trigger():
    """Trigger a Fabric run of NB_LEADERSHIP_SCORECARD_UPDATE. Returns the monitor URL
    for the job instance; UI polls the runs list to see when the new
    PIPELINE_RUN_ID appears in the log."""
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin only"}), 403
    env = _get_env()
    import requests as _requests
    try:
        token = _get_fabric_api_token(env)
    except Exception as e:
        return jsonify({"error": f"Could not acquire Fabric API token: {e}"}), 500
    try:
        nb_id = _resolve_scorecard_notebook_id(env)
    except Exception as e:
        return jsonify({"error": f"Could not resolve notebook: {e}"}), 500
    r = _requests.post(
        f"https://api.fabric.microsoft.com/v1/workspaces/{_SCORECARD_ETL_WORKSPACE_ID}/items/{nb_id}/jobs/instances?jobType=RunNotebook",
        headers={"Authorization": f"Bearer {token}"},
        json={},
        timeout=30,
    )
    if r.status_code not in (200, 202):
        return jsonify({"error": f"Trigger failed: HTTP {r.status_code} {r.text[:400]}"}), 502
    monitor_url = r.headers.get("Location") or r.headers.get("location")
    user_email = (session.get("user", {}) or {}).get("email", "unknown")
    triggered_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return jsonify({
        "ok": True,
        "monitor_url": monitor_url,
        "triggered_at": triggered_at,
        "triggered_by": user_email,
        "notebook_id": nb_id,
        "workspace_id": _SCORECARD_ETL_WORKSPACE_ID,
    })


@scorecard_bp.route("/api/admin/table/<table_key>")
@login_required
def api_admin_table(table_key):
    """Generic read-only TOP N browse for any registry-whitelisted Scorecard
    pipeline table. Supports per-column server-side filtering (contains,
    case-insensitive LIKE with CAST) and per-column server-side sorting
    (overriding the registry default) so column filters requery the full
    source table instead of clipping against the loaded window.

    Query params (all optional):
        col_filters -- JSON `{col: value}` map. `value` may be a string
            (substring LIKE) or a JSON array (exact-match IN clause).
        sort_col / sort_dir -- override registry order_by; sort_dir in ASC/DESC.
        limit -- override TOP N (default 3000, hard cap 10000)."""
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin only"}), 403
    cfg = _load_scorecard_tables().get(table_key)
    if not cfg:
        return jsonify({"error": "unknown table"}), 404
    env = _get_env()

    try:
        col_filters = json.loads(request.args.get("col_filters") or "{}")
    except json.JSONDecodeError:
        return jsonify({"error": "col_filters must be valid JSON"}), 400
    if not isinstance(col_filters, dict):
        return jsonify({"error": "col_filters must be a JSON object"}), 400
    col_filters = _clean_col_filters(col_filters)

    sort_col = (request.args.get("sort_col") or "").strip() or None
    sort_dir = (request.args.get("sort_dir") or "ASC").upper()
    if sort_dir not in ("ASC", "DESC"):
        sort_dir = "ASC"
    try:
        limit = min(int(request.args.get("limit") or 3000), 10000)
        if limit < 1:
            limit = 3000
    except ValueError:
        limit = 3000

    if sort_col and not _IDENTIFIER_RE.match(sort_col):
        return jsonify({"error": f"invalid column name: {sort_col}"}), 400

    try:
        where_parts, where_params = _build_col_filter_where(cfg, env, col_filters)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    where_clause = f" WHERE {' AND '.join(where_parts)}" if where_parts else ""

    sort_python_side = False
    if sort_col:
        if sort_col == "PROPERTY_NAME":
            sort_python_side = True
            order_clause = ""
        else:
            order_clause = f" ORDER BY [{sort_col}] {sort_dir}"
    else:
        default_order = cfg.get("order_by")
        sort_python_side = default_order == "PROPERTY_NAME"
        default_sql_order = cfg.get("sql_order_by") or (default_order if not sort_python_side else None)
        order_clause = f" ORDER BY {default_sql_order}" if default_sql_order else ""

    cfg_out = dict(cfg)
    if where_parts:
        cfg_out["where_sql_resolved"] = " AND ".join(where_parts)
    if order_clause:
        cfg_out["sql_order_by_resolved"] = order_clause.replace(" ORDER BY ", "")
    cfg_out["limit"] = limit

    conn = None
    try:
        conn = SafeConnection(env, cfg["db"], None, direct=cfg.get("direct", False))
    except ValueError as e:
        # Hosted beta on Azure App Service doesn't yet carry Fabric
        # WH_PROD2 credentials (interactive-browser token path only works on
        # the dev workstation). Return a friendly 503 so the UI can show
        # 'not available yet' instead of a raw error string.
        if "No endpoint found" in str(e) or "FABRIC_" in str(e):
            return jsonify({
                "error": (f"Live browse of '{cfg['db']}' source tables is not yet "
                          "available in the hosted beta environment. This table "
                          "is accessible from the dev workstation only until we "
                          "wire up a server-side Fabric token path. "
                          "DB_APP_SUPPORT and DB_BI_SUPPORT tables work fine.")
            }), 503
        raise
    try:
        sql = f"SELECT TOP {limit} * FROM {cfg['schema']}.[{cfg['table']}]{where_clause}{order_clause}"
        cur = conn.execute(sql, where_params if where_params else None)
        columns = [d[0] for d in cur.description]
        rows = cur.fetchall()
        result = []
        for r in rows:
            row_dict = {}
            for i, col in enumerate(columns):
                val = r[i]
                if hasattr(val, "isoformat"):
                    val = val.isoformat()
                row_dict[col] = val
            result.append(row_dict)
    finally:
        conn.close()

    if cfg.get("join_property_name") and "PROPERTY_KEY" in columns:
        name_map = _get_property_name_map(env)
        for row in result:
            pk = row.get("PROPERTY_KEY")
            name = name_map.get(pk)
            row["PROPERTY_NAME"] = name if name else (f"(unknown: {pk})" if pk is not None else "(unknown)")
        columns = ["PROPERTY_NAME"] + [c for c in columns if c != "PROPERTY_NAME"]

    if sort_python_side:
        def _sort_key(r):
            name = r.get("PROPERTY_NAME") or ""
            orphan = name.startswith("(unknown")
            return (1 if orphan else 0, name.lower(), str(r.get("PROPERTY_KEY") or ""))
        result.sort(key=_sort_key, reverse=(sort_dir == "DESC"))

    return jsonify({"columns": columns, "rows": result, "config": cfg_out})


@scorecard_bp.route("/api/admin/table/<table_key>/distinct")
@login_required
def api_admin_table_distinct(table_key):
    """Return TOP 500 DISTINCT values for one column, respecting the OTHER
    column filters currently active (so successive dropdowns cascade like
    Excel). Used by the Table Manager's per-column filter dropdowns."""
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin only"}), 403
    cfg = _load_scorecard_tables().get(table_key)
    if not cfg:
        return jsonify({"error": "unknown table"}), 404

    col = (request.args.get("col") or "").strip()
    if not col or not _IDENTIFIER_RE.match(col):
        return jsonify({"error": "invalid col"}), 400
    search = (request.args.get("search") or "").strip()

    try:
        col_filters = json.loads(request.args.get("col_filters") or "{}")
    except json.JSONDecodeError:
        return jsonify({"error": "col_filters must be valid JSON"}), 400
    if not isinstance(col_filters, dict):
        return jsonify({"error": "col_filters must be a JSON object"}), 400
    col_filters = _clean_col_filters(col_filters)
    col_filters.pop(col, None)  # never restrict the dropdown by its own selection

    env = _get_env()
    try:
        parts, params = _build_col_filter_where(cfg, env, col_filters)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if col == "PROPERTY_NAME":
        if "PROPERTY_KEY" not in _get_table_columns(env, cfg):
            return jsonify({"values": [], "capped": False})
        where = f" WHERE {' AND '.join(parts)}" if parts else ""
        conn = SafeConnection(env, cfg["db"], None, direct=cfg.get("direct", False))
        try:
            sql = f"SELECT DISTINCT TOP 5000 [PROPERTY_KEY] FROM {cfg['schema']}.[{cfg['table']}]{where}"
            cur = conn.execute(sql, params if params else None)
            keys = [r[0] for r in cur.fetchall()]
        finally:
            conn.close()
        name_map = _get_property_name_map(env)
        names = {name_map.get(k) or f"(unknown: {k})" for k in keys if k is not None}
        if search:
            s = search.lower()
            names = {n for n in names if s in n.lower()}
        sorted_names = sorted(names, key=lambda n: (n.startswith("(unknown"), n.lower()))
        return jsonify({"values": sorted_names[:500], "capped": len(sorted_names) > 500})

    if search:
        parts.append(f"CAST([{col}] AS NVARCHAR(400)) LIKE ?")
        params.append(f"%{search}%")
    where = f" WHERE {' AND '.join(parts)}" if parts else ""
    conn = SafeConnection(env, cfg["db"], None, direct=cfg.get("direct", False))
    try:
        sql = f"SELECT DISTINCT TOP 500 [{col}] FROM {cfg['schema']}.[{cfg['table']}]{where} ORDER BY [{col}]"
        cur = conn.execute(sql, params if params else None)
        raw = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()
    values = [v.isoformat() if hasattr(v, "isoformat") else v for v in raw]
    return jsonify({"values": values, "capped": len(values) >= 500})


def _clean_col_filters(col_filters):
    """Normalize col_filters into `{col: str | [values]}`, dropping empties."""
    out = {}
    for k, v in col_filters.items():
        if isinstance(v, list):
            cleaned = [x for x in v if x is not None and str(x).strip() != ""]
            if cleaned:
                out[k] = cleaned
        else:
            s = str(v or "").strip()
            if s != "":
                out[k] = s
    return out


def _build_col_filter_where(cfg, env, col_filters):
    """Build `(where_parts, params)` from cfg.where_sql + col_filters.
    Raises ValueError on bad column names."""
    parts = []
    params = []
    base = cfg.get("where_sql") or ""
    if "{" in base:
        base = base.format(**_get_registry_tokens(env))
    if base:
        parts.append(f"({base})")

    prop_name_val = col_filters.get("PROPERTY_NAME")
    if prop_name_val is not None:
        name_map = _get_property_name_map(env)
        if isinstance(prop_name_val, list):
            wanted = {str(n).lower() for n in prop_name_val}
            matching = [k for k, v in name_map.items() if v and v.lower() in wanted]
        else:
            needle = str(prop_name_val).lower()
            matching = [k for k, v in name_map.items() if v and needle in v.lower()]
        if not matching:
            parts.append("1 = 0")
        else:
            capped = matching[:2000]
            placeholders = ", ".join(["?"] * len(capped))
            parts.append(f"[PROPERTY_KEY] IN ({placeholders})")
            params.extend(capped)

    for col, val in col_filters.items():
        if col == "PROPERTY_NAME":
            continue
        if not _IDENTIFIER_RE.match(col):
            raise ValueError(f"invalid column name: {col}")
        if isinstance(val, list):
            placeholders = ", ".join(["?"] * len(val))
            parts.append(f"CAST([{col}] AS NVARCHAR(400)) IN ({placeholders})")
            params.extend([str(x) for x in val])
        else:
            parts.append(f"CAST([{col}] AS NVARCHAR(400)) LIKE ?")
            params.append(f"%{val}%")
    return parts, params


_table_columns_cache = {}

def _get_table_columns(env, cfg):
    """Cached list of column names for a source table."""
    key = (cfg["db"], cfg["schema"], cfg["table"])
    cached = _table_columns_cache.get(key)
    if cached:
        return cached
    conn = SafeConnection(env, cfg["db"], None, direct=cfg.get("direct", False))
    try:
        cur = conn.execute(f"SELECT TOP 0 * FROM {cfg['schema']}.[{cfg['table']}]")
        cols = [d[0] for d in cur.description]
    finally:
        conn.close()
    _table_columns_cache[key] = cols
    return cols


def _get_current_preleasing_ay(env):
    """Read the AY currently flagged as pre-leasing in ACADEMIC_YEARS."""
    conn = SafeConnection(env, "WH_PROD2", None, direct=False)
    try:
        row = conn.fetchall("SELECT TOP 1 AY_KEY FROM dbo.ACADEMIC_YEARS WHERE FLAG_AY_PRELEASE_AY = 1 ORDER BY AY_KEY DESC")
        if not row:
            raise RuntimeError("No AY with FLAG_AY_PRELEASE_AY = 1")
        return int(row[0][0])
    finally:
        conn.close()


_property_name_cache = {"ts": 0, "map": {}}

def _get_property_name_map(env):
    """PROPERTY_KEY -> PROPERTY_NAME, cached for 5 minutes."""
    import time
    now = time.time()
    if _property_name_cache["map"] and now - _property_name_cache["ts"] < 300:
        return _property_name_cache["map"]
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        rows = conn.fetchall("SELECT PROPERTY_KEY, PROPERTY_NAME FROM dbo.PROPERTY_0")
        name_map = {r[0]: r[1] for r in rows}
        _property_name_cache["map"] = name_map
        _property_name_cache["ts"] = now
        return name_map
    finally:
        conn.close()


_ay_cache = {"ts": 0, "preleasing": None, "current": None}

def _get_registry_tokens(env):
    """Substitution tokens available inside registry `where_sql` templates."""
    import time, datetime as _dt
    now_ts = time.time()
    if _ay_cache["preleasing"] is None or now_ts - _ay_cache["ts"] > 300:
        conn = SafeConnection(env, "WH_PROD2", None, direct=False)
        try:
            rows = conn.fetchall("SELECT AY_KEY, FLAG_AY_PRELEASE_AY, FLAG_AY_CURRENT_AY FROM dbo.ACADEMIC_YEARS WHERE FLAG_AY_PRELEASE_AY = 1 OR FLAG_AY_CURRENT_AY = 1")
            preleasing = next((int(r[0]) for r in rows if r[1] == 1), None)
            current = next((int(r[0]) for r in rows if r[2] == 1), None)
            if preleasing is None or current is None:
                raise RuntimeError("ACADEMIC_YEARS missing preleasing/current AY flags")
            _ay_cache["preleasing"] = preleasing
            _ay_cache["current"] = current
            _ay_cache["ts"] = now_ts
        finally:
            conn.close()
    today = _dt.date.today()
    d120 = today - _dt.timedelta(days=120)
    d200 = today - _dt.timedelta(days=200)
    return {
        "preleasing_ay": _ay_cache["preleasing"],
        "current_ay": _ay_cache["current"],
        "today": today.isoformat(),
        "today_int": int(today.strftime("%Y%m%d")),
        "today_minus_120": d120.isoformat(),
        "today_minus_120_int": int(d120.strftime("%Y%m%d")),
        "today_minus_200": d200.isoformat(),
        "today_minus_200_int": int(d200.strftime("%Y%m%d")),
    }


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@scorecard_bp.route("/api/admin/table/<table_key>/edit", methods=["PATCH"])
@login_required
def api_admin_table_edit(table_key):
    """In-place edit of a single row in a registry-whitelisted table.
    Only fields in the registry's `editable_columns` list can be changed.
    Every edit writes an append-only row to control.SCORECARD_TABLE_MANAGER_AUDIT
    (with old + new value) and upserts dbo.SCORECARD_FIELD_OVERRIDES for
    lock-aware pipeline reads.

    Request body: {"row_key": {<pk_col>: <val>, ...}, "changes": {<col>: <val>, ...},
                    "reason": "optional note"}"""
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin only"}), 403

    cfg = _load_scorecard_tables().get(table_key)
    if not cfg:
        return jsonify({"error": "unknown table"}), 404
    pk_cols = cfg.get("primary_key") or []
    editable = set(cfg.get("editable_columns") or [])
    if not pk_cols or not editable:
        return jsonify({"error": "this table is not editable"}), 400

    payload = request.get_json(silent=True) or {}
    row_key = payload.get("row_key") or {}
    changes = payload.get("changes") or {}
    reason = (payload.get("reason") or "").strip() or None

    if not isinstance(row_key, dict) or set(row_key.keys()) != set(pk_cols):
        return jsonify({"error": f"row_key must contain exactly: {pk_cols}"}), 400
    if not isinstance(changes, dict) or not changes:
        return jsonify({"error": "changes must be a non-empty object"}), 400
    for c in changes:
        if c not in editable:
            return jsonify({"error": f"field '{c}' is not editable for this table"}), 400
        if not _IDENTIFIER_RE.match(c):
            return jsonify({"error": f"field '{c}' has an invalid name"}), 400
    for c in pk_cols:
        if not _IDENTIFIER_RE.match(c):
            return jsonify({"error": f"primary key column '{c}' has an invalid name"}), 400

    user_email = (session.get("user", {}) or {}).get("email", "unknown")
    env = _get_env()
    conn = SafeConnection(env, cfg["db"], None, direct=cfg.get("direct", False))
    conn_bi = SafeConnection(env, "DB_BI_SUPPORT", None, direct=True)
    conn_app = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True) if cfg["db"] != "DB_APP_SUPPORT" else None
    try:
        where_sql = " AND ".join([f"[{c}] = ?" for c in pk_cols])
        pk_values = [row_key[c] for c in pk_cols]
        select_cols_sql = ", ".join([f"[{c}]" for c in changes])
        cur = conn.execute(f"SELECT {select_cols_sql} FROM {cfg['schema']}.[{cfg['table']}] WHERE {where_sql}", pk_values)
        current = cur.fetchone()
        if current is None:
            return jsonify({"error": "row not found"}), 404
        old_values = {c: current[i] for i, c in enumerate(changes)}

        set_sql = ", ".join([f"[{c}] = ?" for c in changes])
        conn.execute(f"UPDATE {cfg['schema']}.[{cfg['table']}] SET {set_sql} WHERE {where_sql}",
                     list(changes.values()) + pk_values)

        row_key_json = json.dumps(row_key, sort_keys=True, default=str)
        for field_name, new_val in changes.items():
            old_val = old_values.get(field_name)
            conn_bi.execute("""
                INSERT INTO control.SCORECARD_TABLE_MANAGER_AUDIT
                    (SOURCE_TABLE_KEY, ROW_KEY, FIELD_NAME, OLD_VALUE, NEW_VALUE, ACTION, CHANGED_BY, REASON)
                VALUES (?, ?, ?, ?, ?, 'UPDATE', ?, ?)
            """, (table_key, row_key_json, field_name,
                  None if old_val is None else str(old_val)[:2000],
                  None if new_val is None else str(new_val)[:2000],
                  user_email, reason))
        conn_bi.commit()

        overrides_conn = conn_app if conn_app is not None else conn
        for field_name, new_val in changes.items():
            cur_upd = overrides_conn.execute("""
                UPDATE dbo.SCORECARD_FIELD_OVERRIDES
                SET OVERRIDE_VALUE = ?, LOCKED = 1, REASON = ?, UPDATED_BY = ?, UPDATED_AT = SYSUTCDATETIME()
                WHERE SOURCE_TABLE_KEY = ? AND ROW_KEY = ? AND FIELD_NAME = ?
            """, (None if new_val is None else str(new_val)[:2000], reason, user_email,
                  table_key, row_key_json, field_name))
            if cur_upd.rowcount == 0:
                overrides_conn.execute("""
                    INSERT INTO dbo.SCORECARD_FIELD_OVERRIDES
                        (SOURCE_TABLE_KEY, ROW_KEY, FIELD_NAME, OVERRIDE_VALUE, LOCKED, REASON, CREATED_BY)
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                """, (table_key, row_key_json, field_name,
                      None if new_val is None else str(new_val)[:2000], reason, user_email))
        overrides_conn.commit()
        conn.commit()

        return jsonify({"ok": True, "updated": list(changes.keys()), "old_values": {k: (None if v is None else str(v)) for k, v in old_values.items()}})
    finally:
        conn.close()
        conn_bi.close()
        if conn_app is not None:
            conn_app.close()


@scorecard_bp.route("/api/admin/table/<table_key>/bulk-edit", methods=["PATCH"])
@login_required
def api_admin_table_bulk_edit(table_key):
    """Apply the same single-field change to N rows. Same validation +
    audit-logging as the single-row edit, but wraps a Python loop so we
    can return per-row success/failure counts.

    Request body: {"row_keys": [{<pk>: v}, ...], "field": "<col>",
                    "value": <new_value>, "reason": "..."}
    """
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin only"}), 403
    cfg = _load_scorecard_tables().get(table_key)
    if not cfg:
        return jsonify({"error": "unknown table"}), 404
    pk_cols = cfg.get("primary_key") or []
    editable = set(cfg.get("editable_columns") or [])
    if not pk_cols or not editable:
        return jsonify({"error": "this table is not editable"}), 400

    payload = request.get_json(silent=True) or {}
    row_keys = payload.get("row_keys") or []
    field = payload.get("field")
    new_val = payload.get("value")
    reason = (payload.get("reason") or "").strip() or None

    if not isinstance(row_keys, list) or not row_keys:
        return jsonify({"error": "row_keys must be a non-empty list"}), 400
    if len(row_keys) > 2000:
        return jsonify({"error": "row_keys capped at 2000 per request"}), 400
    if not field or field not in editable:
        return jsonify({"error": f"field '{field}' is not editable for this table"}), 400
    if not _IDENTIFIER_RE.match(field):
        return jsonify({"error": f"invalid field name: {field}"}), 400
    for rk in row_keys:
        if not isinstance(rk, dict) or set(rk.keys()) != set(pk_cols):
            return jsonify({"error": f"each row_key must contain exactly: {pk_cols}"}), 400
    for c in pk_cols:
        if not _IDENTIFIER_RE.match(c):
            return jsonify({"error": f"invalid primary key column: {c}"}), 400

    user_email = (session.get("user", {}) or {}).get("email", "unknown")
    env = _get_env()
    conn = SafeConnection(env, cfg["db"], None, direct=cfg.get("direct", False))
    conn_bi = SafeConnection(env, "DB_BI_SUPPORT", None, direct=True)
    conn_app = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True) if cfg["db"] != "DB_APP_SUPPORT" else None
    try:
        where_sql = " AND ".join([f"[{c}] = ?" for c in pk_cols])
        updated = 0
        unchanged = 0
        missing = 0
        errors = []
        new_val_stored = None if new_val is None or new_val == "" else str(new_val)
        for rk in row_keys:
            pk_values = [rk[c] for c in pk_cols]
            try:
                cur = conn.execute(f"SELECT [{field}] FROM {cfg['schema']}.[{cfg['table']}] WHERE {where_sql}", pk_values)
                current = cur.fetchone()
                if current is None:
                    missing += 1
                    continue
                old_val = current[0]
                # Compare as strings for consistency with the single-row edit path.
                old_str = "" if old_val is None else str(old_val)
                new_str = "" if new_val_stored is None else str(new_val_stored)
                if old_str == new_str:
                    unchanged += 1
                    continue
                conn.execute(f"UPDATE {cfg['schema']}.[{cfg['table']}] SET [{field}] = ? WHERE {where_sql}",
                             [new_val_stored] + pk_values)

                row_key_json = json.dumps(rk, sort_keys=True, default=str)
                conn_bi.execute("""
                    INSERT INTO control.SCORECARD_TABLE_MANAGER_AUDIT
                        (SOURCE_TABLE_KEY, ROW_KEY, FIELD_NAME, OLD_VALUE, NEW_VALUE, ACTION, CHANGED_BY, REASON)
                    VALUES (?, ?, ?, ?, ?, 'UPDATE', ?, ?)
                """, (table_key, row_key_json, field,
                      None if old_val is None else str(old_val)[:2000],
                      None if new_val_stored is None else str(new_val_stored)[:2000],
                      user_email, reason))
                overrides_conn = conn_app if conn_app is not None else conn
                cur_upd = overrides_conn.execute("""
                    UPDATE dbo.SCORECARD_FIELD_OVERRIDES
                    SET OVERRIDE_VALUE = ?, LOCKED = 1, REASON = ?, UPDATED_BY = ?, UPDATED_AT = SYSUTCDATETIME()
                    WHERE SOURCE_TABLE_KEY = ? AND ROW_KEY = ? AND FIELD_NAME = ?
                """, (None if new_val_stored is None else str(new_val_stored)[:2000], reason, user_email,
                      table_key, row_key_json, field))
                if cur_upd.rowcount == 0:
                    overrides_conn.execute("""
                        INSERT INTO dbo.SCORECARD_FIELD_OVERRIDES
                            (SOURCE_TABLE_KEY, ROW_KEY, FIELD_NAME, OVERRIDE_VALUE, LOCKED, REASON, CREATED_BY)
                        VALUES (?, ?, ?, ?, 1, ?, ?)
                    """, (table_key, row_key_json, field,
                          None if new_val_stored is None else str(new_val_stored)[:2000], reason, user_email))
                updated += 1
            except Exception as row_err:
                errors.append({"row_key": rk, "error": str(row_err)[:200]})
        conn.commit(); conn_bi.commit()
        if conn_app is not None:
            conn_app.commit()

        return jsonify({
            "ok": True,
            "field": field,
            "attempted": len(row_keys),
            "updated": updated,
            "unchanged": unchanged,
            "missing": missing,
            "errors": errors,
        })
    finally:
        conn.close()
        conn_bi.close()
        if conn_app is not None:
            conn_app.close()


@scorecard_bp.route("/api/admin/table/<table_key>", methods=["POST"])
@login_required
def api_admin_table_insert(table_key):
    """Insert a new row into a registry-whitelisted table (requires
    `allow_insert: true`). Values may only contain columns from
    `insertable_columns`. `required_columns` (also from the registry) MUST
    be provided or the insert is rejected before touching the DB. The
    generated identity PK is captured via OUTPUT INSERTED and returned.
    Every column set is logged as its own audit row (ACTION='INSERT',
    old_value=null, new_value=value)."""
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin only"}), 403
    cfg = _load_scorecard_tables().get(table_key)
    if not cfg:
        return jsonify({"error": "unknown table"}), 404
    if not cfg.get("allow_insert"):
        return jsonify({"error": "this table does not allow inserts"}), 400

    insertable = set(cfg.get("insertable_columns") or [])
    required = list(cfg.get("required_columns") or [])
    pk_cols = cfg.get("primary_key") or []
    if not insertable or not pk_cols:
        return jsonify({"error": "insertable_columns / primary_key not configured"}), 400

    payload = request.get_json(silent=True) or {}
    values = payload.get("values") or {}
    reason = (payload.get("reason") or "").strip() or None
    if not isinstance(values, dict) or not values:
        return jsonify({"error": "values must be a non-empty object"}), 400
    for c in values:
        if c not in insertable:
            return jsonify({"error": f"column '{c}' is not insertable for this table"}), 400
        if not _IDENTIFIER_RE.match(c):
            return jsonify({"error": f"column '{c}' has an invalid name"}), 400
    for req in required:
        v = values.get(req)
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return jsonify({"error": f"'{req}' is required"}), 400

    user_email = (session.get("user", {}) or {}).get("email", "unknown")
    env = _get_env()
    conn = SafeConnection(env, cfg["db"], None, direct=cfg.get("direct", False))
    conn_bi = SafeConnection(env, "DB_BI_SUPPORT", None, direct=True)
    try:
        col_list = ", ".join([f"[{c}]" for c in values])
        placeholders = ", ".join(["?"] * len(values))
        # OUTPUT INSERTED so we get the new PK back even for identity columns.
        output_cols = ", ".join([f"INSERTED.[{c}]" for c in pk_cols])
        # Include CREATED_BY if the table has one and we didn't set it explicitly.
        extra_cols = []
        extra_vals = []
        table_cols = _get_table_columns(env, cfg)
        if "CREATED_BY" in table_cols and "CREATED_BY" not in values:
            extra_cols.append("[CREATED_BY]"); extra_vals.append(user_email)
        full_cols = col_list + (", " + ", ".join(extra_cols) if extra_cols else "")
        full_ph = placeholders + (", " + ", ".join(["?"] * len(extra_vals)) if extra_vals else "")
        sql = f"INSERT INTO {cfg['schema']}.[{cfg['table']}] ({full_cols}) OUTPUT {output_cols} VALUES ({full_ph})"
        cur = conn.execute(sql, list(values.values()) + extra_vals)
        new_pk_row = cur.fetchone()
        conn.commit()
        new_row_key = {pk_cols[i]: new_pk_row[i] for i in range(len(pk_cols))}
        row_key_json = json.dumps(new_row_key, sort_keys=True, default=str)

        for field_name, new_val in values.items():
            conn_bi.execute("""
                INSERT INTO control.SCORECARD_TABLE_MANAGER_AUDIT
                    (SOURCE_TABLE_KEY, ROW_KEY, FIELD_NAME, OLD_VALUE, NEW_VALUE, ACTION, CHANGED_BY, REASON)
                VALUES (?, ?, ?, NULL, ?, 'INSERT', ?, ?)
            """, (table_key, row_key_json, field_name,
                  None if new_val is None else str(new_val)[:2000], user_email, reason))
        conn_bi.commit()

        return jsonify({"ok": True, "row_key": new_row_key})
    finally:
        conn.close()
        conn_bi.close()


@scorecard_bp.route("/api/admin/table/<table_key>", methods=["DELETE"])
@login_required
def api_admin_table_delete(table_key):
    """Delete a row from a registry-whitelisted table (requires
    `allow_delete: true`). The row's current values are snapshotted into
    the audit log (ACTION='DELETE', old_value=current, new_value=null) so
    a manual restore has enough information to rebuild the row."""
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin only"}), 403
    cfg = _load_scorecard_tables().get(table_key)
    if not cfg:
        return jsonify({"error": "unknown table"}), 404
    if not cfg.get("allow_delete"):
        return jsonify({"error": "this table does not allow deletes"}), 400
    pk_cols = cfg.get("primary_key") or []
    if not pk_cols:
        return jsonify({"error": "primary_key not configured"}), 400

    payload = request.get_json(silent=True) or {}
    row_key = payload.get("row_key") or {}
    reason = (payload.get("reason") or "").strip() or None
    if not isinstance(row_key, dict) or set(row_key.keys()) != set(pk_cols):
        return jsonify({"error": f"row_key must contain exactly: {pk_cols}"}), 400
    for c in pk_cols:
        if not _IDENTIFIER_RE.match(c):
            return jsonify({"error": f"invalid primary key column: {c}"}), 400

    user_email = (session.get("user", {}) or {}).get("email", "unknown")
    env = _get_env()
    conn = SafeConnection(env, cfg["db"], None, direct=cfg.get("direct", False))
    conn_bi = SafeConnection(env, "DB_BI_SUPPORT", None, direct=True)
    try:
        where_sql = " AND ".join([f"[{c}] = ?" for c in pk_cols])
        pk_values = [row_key[c] for c in pk_cols]
        cur = conn.execute(f"SELECT * FROM {cfg['schema']}.[{cfg['table']}] WHERE {where_sql}", pk_values)
        columns = [d[0] for d in cur.description]
        existing = cur.fetchone()
        if existing is None:
            return jsonify({"error": "row not found"}), 404
        snapshot = {columns[i]: existing[i] for i in range(len(columns))}

        del_cur = conn.execute(f"DELETE FROM {cfg['schema']}.[{cfg['table']}] WHERE {where_sql}", pk_values)
        conn.commit()
        if del_cur.rowcount == 0:
            return jsonify({"error": "row disappeared before delete"}), 409

        row_key_json = json.dumps(row_key, sort_keys=True, default=str)
        for field_name, old_val in snapshot.items():
            if field_name in pk_cols:
                continue  # PKs are captured in row_key
            conn_bi.execute("""
                INSERT INTO control.SCORECARD_TABLE_MANAGER_AUDIT
                    (SOURCE_TABLE_KEY, ROW_KEY, FIELD_NAME, OLD_VALUE, NEW_VALUE, ACTION, CHANGED_BY, REASON)
                VALUES (?, ?, ?, ?, NULL, 'DELETE', ?, ?)
            """, (table_key, row_key_json, field_name,
                  None if old_val is None else str(old_val)[:2000], user_email, reason))
        conn_bi.commit()

        return jsonify({"ok": True, "deleted": row_key})
    finally:
        conn.close()
        conn_bi.close()


@scorecard_bp.route("/api/admin/table/<table_key>/audit")
@login_required
def api_admin_table_audit(table_key):
    """Return the most-recent edit history for a table (TOP 500).
    Optional `row_key` query param filters to a specific row (JSON-encoded
    same as the PATCH endpoint uses)."""
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin only"}), 403
    if not _load_scorecard_tables().get(table_key):
        return jsonify({"error": "unknown table"}), 404

    row_key_param = request.args.get("row_key")
    row_key_json = None
    if row_key_param:
        try:
            parsed = json.loads(row_key_param)
        except json.JSONDecodeError:
            return jsonify({"error": "row_key must be valid JSON"}), 400
        row_key_json = json.dumps(parsed, sort_keys=True, default=str)

    env = _get_env()
    conn_bi = SafeConnection(env, "DB_BI_SUPPORT", None, direct=True)
    try:
        if row_key_json is not None:
            rows = conn_bi.fetchall("""
                SELECT TOP 500 AUDIT_ID, ROW_KEY, FIELD_NAME, OLD_VALUE, NEW_VALUE, ACTION, CHANGED_BY, CHANGED_AT, REASON
                FROM control.SCORECARD_TABLE_MANAGER_AUDIT
                WHERE SOURCE_TABLE_KEY = ? AND ROW_KEY = ?
                ORDER BY AUDIT_ID DESC
            """, (table_key, row_key_json))
        else:
            rows = conn_bi.fetchall("""
                SELECT TOP 500 AUDIT_ID, ROW_KEY, FIELD_NAME, OLD_VALUE, NEW_VALUE, ACTION, CHANGED_BY, CHANGED_AT, REASON
                FROM control.SCORECARD_TABLE_MANAGER_AUDIT
                WHERE SOURCE_TABLE_KEY = ?
                ORDER BY AUDIT_ID DESC
            """, (table_key,))
        result = []
        for r in rows:
            result.append({
                "audit_id": r[0], "row_key": r[1], "field": r[2],
                "old_value": r[3], "new_value": r[4], "action": r[5],
                "changed_by": r[6],
                "changed_at": r[7].isoformat() if r[7] else None,
                "reason": r[8],
            })
        return jsonify({"audit": result})
    finally:
        conn_bi.close()


@scorecard_bp.route("/api/whoami")
@login_required
def whoami():
    """Diagnostic endpoint -- confirms Emp_Core identity resolution end-to-end."""
    check = _require_access()
    if check:
        return check
    user = session.get("user", {})
    profile = get_rm_profile(user.get("email", "")) if user.get("email") else None
    return jsonify({"session_email": user.get("email"), "emp_core_profile": profile})


# ── "View as RM" admin simulation ────────────────────────────────────────
# Lets a real admin browse the Scorecard exactly as any RM would see it,
# for testing that RM_EMAIL scoping actually works in every view/list/API.
# Session key sc_view_as_email holds the target email; when set, _is_admin
# returns False and _effective_rm_email returns that email for scoping.

@scorecard_bp.route("/api/admin/rms")
@login_required
def api_admin_rms():
    """List distinct RM_EMAIL / RM_NAME pairs from dbo.PROPERTY_0 (the
    authoritative source for property assignments) so the 'View as RM'
    picker reflects current reality, not the last pipeline snapshot.
    Real-admin only (uses _is_real_admin so it stays available while
    simulating)."""
    check = _require_access()
    if check:
        return check
    if not _is_real_admin():
        return jsonify({"error": "admin only"}), 403
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        rows = conn.fetchall("""
            SELECT DISTINCT RM_EMAIL, RM_NAME
            FROM dbo.PROPERTY_0
            WHERE FLAG_REPORTABLE = 1 AND RM_EMAIL IS NOT NULL AND RM_EMAIL <> ''
            ORDER BY RM_NAME
        """)
        return jsonify({"rms": [{"email": r[0], "name": r[1] or r[0]} for r in rows]})
    finally:
        conn.close()


@scorecard_bp.route("/api/admin/view-as-rm", methods=["POST"])
@login_required
def api_admin_view_as_rm():
    """Activate the 'view as RM' simulation. Requires the caller to be a
    real admin. Payload: {'email': '<rm_email>'}."""
    check = _require_access()
    if check:
        return check
    if not _is_real_admin():
        return jsonify({"error": "admin only"}), 403
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "email required"}), 400
    session.pop("sc_view_as_pm_property_key", None)  # RM and PM simulation are mutually exclusive
    session.pop("sc_view_as_rvp_email", None)
    session["sc_view_as_email"] = email
    return jsonify({"ok": True, "view_as_email": email})


@scorecard_bp.route("/api/admin/pms")
@login_required
def api_admin_pms():
    """List active Property Managers from Emp_Core so the 'View as PM' picker
    can populate. Real-admin only. Returns email + name + PROPERTY_KEY +
    PROPERTY_NAME (joined against the property's row in SCORECARD_CORE for
    the current AY/QUARTER so the display shows the property they'd see)."""
    check = _require_access()
    if check:
        return check
    if not _is_real_admin():
        return jsonify({"error": "admin only"}), 403
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        rows = conn.fetchall("""
            SELECT DISTINCT e.EMAIL, e.NAME_FULL, e.PROPERTY_KEY,
                   (SELECT TOP 1 PROPERTY_NAME FROM dbo.SCORECARD_CORE sc
                    WHERE sc.PROPERTY_KEY = e.PROPERTY_KEY AND sc.FLAG_CURRENT = 1) AS PROPERTY_NAME
            FROM dbo.Emp_Core e
            WHERE e.FLAG_CURRENT = 1
              AND e.FLAG_ACTIVE = 1
              AND e.TITLE_GROUP LIKE '%Property Manager%'
              AND e.PROPERTY_KEY IS NOT NULL
              AND e.EMAIL IS NOT NULL AND e.EMAIL <> ''
            ORDER BY e.NAME_FULL
        """)
        return jsonify({"pms": [
            {"email": r[0], "name": r[1] or r[0], "property_key": r[2], "property_name": r[3] or f"Property {r[2]}"}
            for r in rows
        ]})
    finally:
        conn.close()


@scorecard_bp.route("/api/admin/view-as-pm", methods=["POST"])
@login_required
def api_admin_view_as_pm():
    """Activate the 'view as PM' simulation. Real-admin only.
    Payload: {'property_key': <int>}."""
    check = _require_access()
    if check:
        return check
    if not _is_real_admin():
        return jsonify({"error": "admin only"}), 403
    payload = request.get_json(silent=True) or {}
    try:
        prop_key = int(payload.get("property_key"))
    except (TypeError, ValueError):
        return jsonify({"error": "property_key required (int)"}), 400
    session.pop("sc_view_as_email", None)  # PM and RM simulation are mutually exclusive
    session.pop("sc_view_as_rvp_email", None)
    session["sc_view_as_pm_property_key"] = prop_key
    return jsonify({"ok": True, "view_as_pm_property_key": prop_key})


@scorecard_bp.route("/api/admin/rvps")
@login_required
def api_admin_rvps():
    """List distinct RVP_EMAIL / RVP_NAME pairs from dbo.PROPERTY_0 for the
    'View as RVP' picker. Also includes any RVP-titled leader in the all-
    properties override set (Sr VP Ops etc.) so admins can simulate them
    even though they have no direct RVP_EMAIL assignments. Real-admin only."""
    check = _require_access()
    if check:
        return check
    if not _is_real_admin():
        return jsonify({"error": "admin only"}), 403
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        rows = conn.fetchall("""
            SELECT DISTINCT RVP_EMAIL, RVP_NAME
            FROM dbo.PROPERTY_0
            WHERE FLAG_REPORTABLE = 1 AND RVP_EMAIL IS NOT NULL AND RVP_EMAIL <> '' AND RVP_EMAIL <> '--'
            ORDER BY RVP_NAME
        """)
        rvps = [{"email": r[0], "name": r[1] or r[0], "sees_all": False} for r in rows]
        known = {r["email"].lower() for r in rvps}
        for extra_email in _RVP_ALL_PROPERTIES_EMAILS:
            if extra_email not in known:
                extra = conn.fetchall(
                    "SELECT TOP 1 NAME_FULL FROM dbo.Emp_Core WHERE LOWER(EMAIL) = ? AND FLAG_CURRENT = 1",
                    (extra_email,))
                name = extra[0][0] if extra else extra_email
                rvps.append({"email": extra_email, "name": name, "sees_all": True})
        for r in rvps:
            if r["email"].lower() in _RVP_ALL_PROPERTIES_EMAILS:
                r["sees_all"] = True
        return jsonify({"rvps": sorted(rvps, key=lambda x: x["name"] or "")})
    finally:
        conn.close()


@scorecard_bp.route("/api/admin/view-as-rvp", methods=["POST"])
@login_required
def api_admin_view_as_rvp():
    """Activate the 'view as RVP' simulation. Real-admin only.
    Payload: {'email': '<rvp_email>'}."""
    check = _require_access()
    if check:
        return check
    if not _is_real_admin():
        return jsonify({"error": "admin only"}), 403
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "email required"}), 400
    session.pop("sc_view_as_email", None)
    session.pop("sc_view_as_pm_property_key", None)
    session["sc_view_as_rvp_email"] = email
    return jsonify({"ok": True, "view_as_rvp_email": email})


@scorecard_bp.route("/api/admin/view-as-clear", methods=["POST"])
@login_required
def api_admin_view_as_clear():
    """Exit any active 'view as' simulation (RM / PM / RVP). Available to
    real admins (so they can toggle back) AND to anyone whose session has
    the key set (so a stale key from a demoted user can always be cleared)."""
    check = _require_access()
    if check:
        return check
    session.pop("sc_view_as_email", None)
    session.pop("sc_view_as_pm_property_key", None)
    session.pop("sc_view_as_rvp_email", None)
    return jsonify({"ok": True})


@scorecard_bp.route("/api/data")
@login_required
def api_data():
    """Read-only SCORECARD_CORE grid data for the Phase 2 table -- scoped to
    the signed-in RM's own portfolio (RM_EMAIL match) unless the user is an
    admin/developer, in which case every property is returned. Always
    resolves the most recent AY/QUARTER actually present in the table (the
    last quarter the pipeline has been run for). ?prior=1 also returns the
    previous quarter's PRERM/LDRTOTAL/MSTOTAL totals for the Q1-history
    toggle (full raw-measure history is not carried -- only the 3 rollups,
    a deliberately scoped-down v1 of the original app's full column
    duplication)."""
    check = _require_access()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        admin = _is_admin()

        latest = conn.fetchall("""
            SELECT TOP 1 AY, QUARTER FROM dbo.SCORECARD_CORE
            WHERE FLAG_CURRENT = 1
            ORDER BY AY DESC, CAST(SUBSTRING(QUARTER, 2, 1) AS INT) DESC
        """)
        if not latest:
            return jsonify({"ay": None, "quarter": None, "quarter_label": None, "is_admin": admin, "rows": [], "prior_quarter": None})
        ay, quarter = latest[0][0], latest[0][1]

        all_cols = _GRID_COLUMNS + _LOCK_COLUMNS + _LOCK_BY_COLUMNS + _REASON_COLUMNS
        # PROPERTY_0 is the authoritative source for RM assignment + property type;
        # SCORECARD_CORE's copies can lag the last pipeline run. Prefer PROPERTY_0
        # via COALESCE so a fresh reassignment shows up immediately in the UI.
        p0_overrides = {"PROPERTY_TYPE", "RM_EMAIL", "RM_NAME"}
        cols_sql = ", ".join(
            f"COALESCE(p.{c}, sc.{c}) AS {c}" if c in p0_overrides and c != "PROPERTY_TYPE"
            else "p.PROPERTY_TYPE" if c == "PROPERTY_TYPE"
            else f"sc.{c}"
            for c in all_cols
        )
        base_from = "FROM dbo.SCORECARD_CORE sc LEFT JOIN dbo.PROPERTY_0 p ON p.PROPERTY_KEY = sc.PROPERTY_KEY"
        where_sql, where_params = _scope_clause("sc")
        rows = conn.fetchall(f"""
            SELECT {cols_sql} {base_from}
            WHERE sc.FLAG_CURRENT = 1 AND sc.AY = ? AND sc.QUARTER = ? AND {where_sql}
            ORDER BY sc.PROPERTY_NAME
        """, tuple([ay, quarter] + where_params))
        data = [dict(zip(all_cols, r)) for r in rows]
        for r in data:
            r["OVERALL"] = (r["LDRTOTAL"] or 0) + (r["MSTOTAL"] or 0)

        prior_payload = None
        if request.args.get("prior") == "1":
            q_num = int(quarter[1])
            prev_ay, prev_q = (ay - 1, "Q4") if q_num == 1 else (ay, f"Q{q_num - 1}")
            prior_cols = ["PROPERTY_KEY", "PRERM", "LDRTOTAL", "MSTOTAL"]
            prior_rows = conn.fetchall(f"""
                SELECT sc.PROPERTY_KEY, sc.PRERM, sc.LDRTOTAL, sc.MSTOTAL
                FROM dbo.SCORECARD_CORE sc LEFT JOIN dbo.PROPERTY_0 p ON p.PROPERTY_KEY = sc.PROPERTY_KEY
                WHERE sc.FLAG_CURRENT = 1 AND sc.AY = ? AND sc.QUARTER = ? AND {where_sql}
            """, tuple([prev_ay, prev_q] + where_params))
            prior_payload = {
                "ay": prev_ay, "quarter": prev_q, "quarter_label": f"{prev_q} {prev_ay}",
                "rows": [dict(zip(prior_cols, r)) for r in prior_rows],
            }
            for r in prior_payload["rows"]:
                r["OVERALL"] = (r["LDRTOTAL"] or 0) + (r["MSTOTAL"] or 0)

        return jsonify({
            "ay": ay, "quarter": quarter, "quarter_label": f"{quarter} {ay}",
            "is_admin": admin,
            "rows": data,
            "prior_quarter": prior_payload,
        })
    finally:
        conn.close()


def _latest_period(conn):
    latest = conn.fetchall("""
        SELECT TOP 1 AY, QUARTER FROM dbo.SCORECARD_CORE
        WHERE FLAG_CURRENT = 1
        ORDER BY AY DESC, CAST(SUBSTRING(QUARTER, 2, 1) AS INT) DESC
    """)
    return (latest[0][0], latest[0][1]) if latest else (None, None)


def _scoped_property_row(conn, property_key, ay, quarter, admin, email, cols):
    """Return the requested SCORECARD_CORE columns for one property IF the
    current user's role scope grants access, else None.
    `admin` and `email` are accepted for backward compatibility but the
    scope is now derived from the session via _scope_clause() -- covers
    admin / pm / rvp / rm uniformly. PROPERTY_TYPE + RM_EMAIL/RM_NAME come
    from PROPERTY_0 so fresh reassignments are honored immediately."""
    p0_overrides = {"RM_EMAIL", "RM_NAME"}
    def _col_sql(c):
        if c == "PROPERTY_TYPE":
            return "p.PROPERTY_TYPE"
        if c in p0_overrides:
            return f"COALESCE(p.{c}, sc.{c}) AS {c}"
        return f"sc.{c}"
    cols_sql = ", ".join(_col_sql(c) for c in cols)
    base = "FROM dbo.SCORECARD_CORE sc LEFT JOIN dbo.PROPERTY_0 p ON p.PROPERTY_KEY = sc.PROPERTY_KEY"
    where_sql, where_params = _scope_clause("sc")
    rows = conn.fetchall(
        f"SELECT {cols_sql} {base} WHERE sc.PROPERTY_KEY = ? AND sc.AY = ? AND sc.QUARTER = ? AND sc.FLAG_CURRENT = 1 AND {where_sql}",
        tuple([property_key, ay, quarter] + where_params))
    return rows[0] if rows else None


@scorecard_bp.route("/api/property/<int:property_key>")
@login_required
def api_property_detail(property_key):
    """Full measure detail (value + <measure>_LOCKED bit) for the override
    slideout -- one property, the current AY/QUARTER only. Scoped the same
    way as /api/data (own portfolio unless admin/developer)."""
    check = _require_access()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        admin = _is_admin()
        email = _effective_rm_email()
        ay, quarter = _latest_period(conn)
        if ay is None:
            return jsonify({"error": "no data available"}), 404

        cols = ["PROPERTY_KEY", "PROPERTY_NAME", "ENTITY_NUMBER", "RM_NAME", "RM_EMAIL", "QUARTER_YEAR"]
        for k in _MEASURE_KEYS:
            cols += [k, f"{k}_LOCKED", f"{k}_LOCKED_BY", f"{k}_REASON"]
        cols += ["PRERM", "LDRTOTAL", "MSTOTAL", "NOTES", "NOTE_BY", "NOTE_AT", "EXCEPTION_LABEL"]

        row = _scoped_property_row(conn, property_key, ay, quarter, admin, email, cols)
        if row is None:
            return jsonify({"error": "not found or not authorized"}), 404
        data = dict(zip(cols, row))
        data["OVERALL"] = (data["LDRTOTAL"] or 0) + (data["MSTOTAL"] or 0)
        data["is_admin"] = admin
        # Reaching this line already proves the caller is either an admin or
        # the RM who owns this property (see _scoped_property_row) -- both
        # are allowed to override, per stakeholder direction 2026-09-22.
        # PMs are always read-only regardless of ownership match.
        data["can_edit"] = not _is_pm()
        return jsonify(data)
    finally:
        conn.close()


@scorecard_bp.route("/api/property/<int:property_key>/why-summary")
@login_required
def api_property_why_summary(property_key):
    """Per-property tailored "how was this scored?" summary. Reads the property's
    row + queries source tables for measures where we can compute a concrete
    number (transactions counted, avg open days, etc.) and returns a plain-English
    sentence per measure. Fallback to a generic pass/fail sentence for measures
    we don't yet summarize with hard numbers (TC, TR, REP, RA)."""
    check = _require_access()
    if check:
        return check
    env = _get_env()
    conn_app = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        admin = _is_admin()
        email = _effective_rm_email()
        ay, quarter = _latest_period(conn_app)
        if ay is None:
            return jsonify({"error": "no data available"}), 404
        cols = ["PROPERTY_KEY", "PROPERTY_NAME", "ENTITY_NUMBER"]
        for k in _MEASURE_KEYS:
            cols += [k, f"{k}_LOCKED", f"{k}_LOCKED_BY", f"{k}_REASON"]
        row = _scoped_property_row(conn_app, property_key, ay, quarter, admin, email, cols)
        if row is None:
            return jsonify({"error": "not found or not authorized"}), 404
        property_row = dict(zip(cols, row))
    finally:
        conn_app.close()
    summaries = _build_measure_summaries(env, property_key, property_row, ay, quarter)
    return jsonify({"summaries": summaries, "quarter_label": f"{quarter} {ay}"})


def _build_measure_summaries(env, property_key, property_row, ay, quarter):
    """Per-measure tailored text for the "How was this scored?" slideout. One
    dict per measure with {status, text}."""
    q_start, q_end = _quarter_bounds(ay, quarter)
    q_start_int = int(q_start.strftime("%Y%m%d"))
    q_end_int = int(q_end.strftime("%Y%m%d"))
    summaries = {}
    conn_wh = SafeConnection(env, "WH_PROD2", None)
    try:
        # PCARD: count Prepaid Visa transactions in the quarter
        try:
            r = conn_wh.fetchall("""
                SELECT COUNT(*) FROM dbo.LS_PREPAID_VISA
                WHERE PROPERTY_KEY = ? AND PROPERTY_KEY IS NOT NULL
                      AND DATETIME_RECONCILIATION BETWEEN ? AND ?
            """, (property_key, q_start, q_end))
            cnt = r[0][0] if r else 0
            if cnt == 0:
                summaries["PCARD"] = {"status": "pass", "text": f"PASSED. Zero prepaid Visa transactions in {quarter} {ay}. Rule: any transaction = fail."}
            else:
                summaries["PCARD"] = {"status": "fail", "text": f"FAILED. This property had {cnt} prepaid Visa transaction{'s' if cnt != 1 else ''} in {quarter} {ay}. Rule: zero transactions required to pass."}
        except Exception as e:
            summaries["PCARD"] = {"status": "generic", "text": f"(Could not summarize: {e})"}

        # IIPP / LFA / PMLEO / MSLEO: monthly LEO snapshots
        leo_map = {"IIPP": "IIPP_COMPLETE", "LFA": "LEASE_FILE_AUDIT_COMPLETE",
                   "PMLEO": "BONUS_PM_SCORE", "MSLEO": "BONUS_MS_SCORE"}
        for m, col in leo_map.items():
            try:
                r = conn_wh.fetchall(f"""
                    SELECT COUNT(*), SUM(CASE WHEN [{col}] = 0 THEN 1 ELSE 0 END)
                    FROM dbo.LEO_COMPLIANCE_EXPORT_FACT
                    WHERE PROPERTY_KEY = ? AND DATE_KEY BETWEEN ? AND ?
                """, (property_key, q_start_int, q_end_int))
                total, failing = (r[0][0], r[0][1] or 0) if r else (0, 0)
                if total == 0:
                    summaries[m] = {"status": "nodata", "text": f"No LEO Compliance snapshots recorded for this property in {quarter} {ay}. Rule defaults such properties to PASS."}
                elif failing > 0:
                    summaries[m] = {"status": "fail", "text": f"FAILED. {failing} of {total} monthly LEO snapshot{'s' if total != 1 else ''} for {m} showed incomplete in {quarter} {ay}. Rule: any monthly incomplete = quarter fails."}
                else:
                    summaries[m] = {"status": "pass", "text": f"PASSED. All {total} monthly LEO snapshot{'s' if total != 1 else ''} for {m} showed complete in {quarter} {ay}."}
            except Exception as e:
                summaries[m] = {"status": "generic", "text": f"(Could not summarize: {e})"}

        # CURB / PUBLICAREAS / MAINT / LOGS: RM Quarterly Inspection scores.
        # When a property has more than one inspection record for the quarter,
        # apply "best score of any inspection" per column (stakeholder decision
        # 2026-09-30). NULLs are ignored so a partial second inspection can't
        # override a valid earlier one.
        insp_map = {"CURB": "SCORE_CURB_APPEAL", "PUBLICAREAS": "SCORE_PUBLIC_AREAS_AND_AMENITIES",
                    "MAINT": "SCORE_MAINTENANCE", "LOGS": "SCORE_LOGS_AND_BINDERS"}
        try:
            r = conn_wh.fetchall("""
                SELECT MAX(CAST(SCORE_CURB_APPEAL             AS DECIMAL(10,4))),
                       MAX(CAST(SCORE_PUBLIC_AREAS_AND_AMENITIES AS DECIMAL(10,4))),
                       MAX(CAST(SCORE_MAINTENANCE            AS DECIMAL(10,4))),
                       MAX(CAST(SCORE_LOGS_AND_BINDERS       AS DECIMAL(10,4))),
                       COUNT(*)
                FROM dbo.LS_RM_QUARTERLY_INSPECTION_SCORES_FACT
                WHERE PROPERTY_KEY = ? AND AY = ? AND QUARTER = ?
            """, (property_key, ay, quarter))
            insp_count = int(r[0][4]) if r and r[0][4] is not None else 0
            if insp_count > 0:
                insp_qualifier = f"best of {insp_count} inspection{'s' if insp_count != 1 else ''}"
                for i, m in enumerate(insp_map):
                    score = r[0][i]
                    if score is None:
                        summaries[m] = {"status": "nodata", "text": f"RM Inspection did not include a {m} score for {quarter} {ay}."}
                    elif float(score) >= 85:
                        summaries[m] = {"status": "pass", "text": f"PASSED. RM Inspection {m} score ({insp_qualifier}) for {quarter} {ay} = {float(score):.2f}. Rule: best score of any inspection this quarter, >= 85 to pass."}
                    else:
                        summaries[m] = {"status": "fail", "text": f"FAILED. RM Inspection {m} score ({insp_qualifier}) for {quarter} {ay} = {float(score):.2f} (needed >= 85 to pass, using the best score of any inspection this quarter)."}
            else:
                for m in insp_map:
                    summaries[m] = {"status": "nodata", "text": f"No RM Quarterly Inspection recorded for this property in {quarter} {ay}."}
        except Exception as e:
            for m in insp_map:
                summaries[m] = {"status": "generic", "text": f"(Could not summarize: {e})"}

        # WO / MSWO: avg net open days across completed work orders in the quarter
        try:
            r = conn_wh.fetchall("""
                SELECT AVG(CAST(NET_OPEN_DAY_COUNT AS DECIMAL(10,2))), COUNT(*)
                FROM dbo.WORK_ORDER_REQUESTS
                WHERE PROPERTY_KEY = ? AND STATUS IN ('Complete', 'COMPLETED')
                      AND COMPLETED_DATE BETWEEN ? AND ?
                      AND NET_OPEN_DAY_COUNT IS NOT NULL
            """, (property_key, q_start, q_end))
            avg_days, wo_count = (r[0][0], r[0][1] or 0) if r else (None, 0)
            for m in ["WO", "MSWO"]:
                if wo_count == 0:
                    summaries[m] = {"status": "nodata", "text": f"No completed work orders recorded for this property in {quarter} {ay}."}
                else:
                    avg_val = float(avg_days) if avg_days is not None else 0
                    if avg_val <= 1.0:
                        summaries[m] = {"status": "pass", "text": f"PASSED. Avg net open days across {wo_count} completed work order{'s' if wo_count != 1 else ''} in {quarter} {ay} = {avg_val:.2f}. Rule: <= 1 day to pass."}
                    else:
                        summaries[m] = {"status": "fail", "text": f"FAILED. Avg net open days across {wo_count} completed work order{'s' if wo_count != 1 else ''} in {quarter} {ay} = {avg_val:.2f} (needed <= 1 day)."}
        except Exception as e:
            for m in ["WO", "MSWO"]:
                summaries[m] = {"status": "generic", "text": f"(Could not summarize: {e})"}

        # TR (Training Compliance): average of monthly compliance % rows across the quarter
        try:
            dk_start = int(q_start.strftime("%Y%m%d"))
            dk_end = int(q_end.strftime("%Y%m%d"))
            r = conn_wh.fetchall("""
                SELECT DATE_KEY, COMPLIANCE_PERCENTAGE
                FROM dbo.GRACEHILL_LOCATION_COMPLIANCE_IMPORT_FACT
                WHERE PROPERTY_KEY = ? AND DATE_KEY >= ? AND DATE_KEY <= ?
                      AND COMPLIANCE_PERCENTAGE IS NOT NULL
                ORDER BY DATE_KEY
            """, (property_key, dk_start, dk_end))
            vals = [float(pct) for _, pct in r]
            if not vals:
                summaries["TR"] = {"status": "nodata", "text": f"No Gracehill compliance data recorded for this property in {quarter} {ay}. Per the rule, missing data defaults to PASS."}
            else:
                avg_pct = sum(vals) / len(vals)
                pct_disp = avg_pct * 100 if avg_pct <= 1.5 else avg_pct
                if avg_pct >= 0.94:
                    summaries["TR"] = {"status": "pass", "text": f"PASSED. Avg Gracehill compliance across {len(vals)} monthly snapshot{'s' if len(vals) != 1 else ''} in {quarter} {ay} = {pct_disp:.1f}%. Rule: >= 94% to pass."}
                else:
                    summaries["TR"] = {"status": "fail", "text": f"FAILED. Avg Gracehill compliance across {len(vals)} monthly snapshot{'s' if len(vals) != 1 else ''} in {quarter} {ay} = {pct_disp:.1f}% (needed >= 94%)."}
        except Exception as e:
            summaries["TR"] = {"status": "generic", "text": f"(Could not summarize TR: {e})"}

        # RA (Risk Assessment): count Complete vs non-Complete action items
        try:
            r = conn_wh.fetchall("""
                SELECT STATUS, COUNT(*) FROM dbo.LS_COMPLIANCE_IMPORT
                WHERE PROPERTY_KEY = ?
                GROUP BY STATUS
            """, (property_key,))
            if not r:
                summaries["RA"] = {"status": "nodata", "text": f"No Risk Assessment action items recorded for this property. Per the rule, missing data defaults to PASS."}
            else:
                by = {(s or "").strip(): int(c) for s, c in r}
                complete_n = by.get("Complete", 0)
                total = sum(by.values())
                incomplete_n = total - complete_n
                if incomplete_n == 0:
                    summaries["RA"] = {"status": "pass", "text": f"PASSED. All {total} Risk Assessment action item{'s' if total != 1 else ''} for this property are Complete."}
                else:
                    parts = [f"{n} {s}" for s, n in sorted(by.items()) if s != "Complete"]
                    summaries["RA"] = {"status": "fail", "text": f"FAILED. Of {total} Risk Assessment action items, {complete_n} Complete and {incomplete_n} not Complete ({', '.join(parts)}). Rule: 100% must be Complete."}
        except Exception as e:
            summaries["RA"] = {"status": "generic", "text": f"(Could not summarize RA: {e})"}

        # REP (Reputation): quarter-over-quarter % change between closing-Friday snapshots
        try:
            prev_q_end = q_start - datetime.timedelta(days=1)
            f_curr = _last_friday_on_or_before(q_end)
            f_prev = _last_friday_on_or_before(prev_q_end)
            r = conn_wh.fetchall("""
                SELECT CAST(DATERANGETO AS DATE), SCORE
                FROM dbo.REPUTATION_COM_SUMMARY_FACT
                WHERE PROPERTY_KEY = ? AND SCORE IS NOT NULL
                      AND CAST(DATERANGETO AS DATE) IN (?, ?)
            """, (property_key, f_curr, f_prev))
            by_date = {row[0]: float(row[1]) for row in r}
            curr, prev = by_date.get(f_curr), by_date.get(f_prev)
            if curr is None or prev is None:
                summaries["REP"] = {"status": "nodata", "text": f"Reputation.com snapshots for {quarter} {ay} closing-Friday comparison are not both present (this quarter's Friday {f_curr}: {'yes' if curr is not None else 'missing'}, prior quarter's Friday {f_prev}: {'yes' if prev is not None else 'missing'}). Per the rule, missing data defaults to PASS."}
            elif prev == 0:
                summaries["REP"] = {"status": "nodata", "text": f"Cannot compute % change -- prior quarter's Reputation score was 0."}
            else:
                pct_change = (curr - prev) / prev
                if pct_change > 0.01:
                    summaries["REP"] = {"status": "pass", "text": f"PASSED. Reputation score improved from {prev:.2f} ({f_prev}) to {curr:.2f} ({f_curr}) = +{pct_change * 100:.2f}%. Rule: > +1% improvement to pass."}
                else:
                    summaries["REP"] = {"status": "fail", "text": f"FAILED. Reputation score went from {prev:.2f} ({f_prev}) to {curr:.2f} ({f_curr}) = {pct_change * 100:+.2f}% (needed > +1%)."}
        except Exception as e:
            summaries["REP"] = {"status": "generic", "text": f"(Could not summarize REP: {e})"}

        # TC (Timecard Approvals): count of Supervisor approvals in the quarter.
        # Full on-time/late calc requires the NY / West-Coast due-date calendars
        # and per-row buffer arithmetic -- that lives on the drilldown page. We
        # summarize the row count here so the RM knows how many approvals landed
        # in the quarter, and defer the breakdown of on-time vs late to the
        # drilldown click-through.
        try:
            entity_number = property_row.get("ENTITY_NUMBER")
            if entity_number is not None:
                # DEPARTMENT_CODE in LS_TIMESHEET is the entity number (possibly
                # zero-padded or with a suffix). Match on the leading digits.
                r = conn_wh.fetchall("""
                    SELECT COUNT(*)
                    FROM dbo.LS_TIMESHEET
                    WHERE APRROVAL_TYPE = 'Supervisor'
                      AND DATE_APPROVED BETWEEN ? AND ?
                      AND (DEPARTMENT_CODE = ? OR DEPARTMENT_CODE LIKE ? + '%')
                """, (q_start, q_end, str(entity_number), str(entity_number)))
                approvals = int(r[0][0]) if r else 0
            else:
                approvals = 0
            tc_val = property_row.get("TC")
            if approvals == 0:
                summaries["TC"] = {"status": "nodata", "text": f"No Supervisor timecard approvals recorded for entity {entity_number} in {quarter} {ay}. Per the rule, missing data defaults to PASS."}
            elif tc_val:
                summaries["TC"] = {"status": "pass", "text": f"PASSED. {approvals} Supervisor timecard approval{'s' if approvals != 1 else ''} recorded for entity {entity_number} in {quarter} {ay}. Rule: ~100% approved on time (NY/Non-NY due-date calendars + buffer). Click the measure header for the per-approval on-time/late breakdown."}
            else:
                summaries["TC"] = {"status": "fail", "text": f"FAILED. {approvals} Supervisor timecard approval{'s' if approvals != 1 else ''} recorded for entity {entity_number} in {quarter} {ay}, but at least one was late per the NY/Non-NY due-date + buffer rule. Click the measure header for the per-approval breakdown."}
        except Exception as e:
            summaries["TC"] = {"status": "generic", "text": f"(Could not summarize TC: {e})"}
    finally:
        conn_wh.close()

    # Subjective measures: use property_row directly (no DB query needed)
    rm_val = property_row.get("RMSCORE")
    if rm_val is None:
        summaries["RMSCORE"] = {"status": "nodata", "text": "Not yet entered. This is the RM's subjective 0-5 rating of the Property Manager's leadership this quarter."}
    else:
        summaries["RMSCORE"] = {"status": "info", "text": f"RM entered {rm_val} / 5."}
    surveys_val = property_row.get("SURVEYS")
    if surveys_val is None:
        summaries["SURVEYS"] = {"status": "nodata", "text": "Not yet entered by the RM."}
    else:
        summaries["SURVEYS"] = {"status": "pass" if surveys_val else "fail", "text": f"RM entered: {'Yes (surveys completed).' if surveys_val else 'No (surveys not completed).'}"}
    noi_val = property_row.get("NOI")
    if noi_val is None:
        summaries["NOI"] = {"status": "nodata", "text": "Not yet entered by the RM. NOI is manually entered here; there is no automated file feed today."}
    else:
        summaries["NOI"] = {"status": "pass" if noi_val else "fail", "text": f"RM entered: {'Yes (NOI met budget).' if noi_val else 'No (NOI did not meet budget).'}"}

    # Measures we don't yet summarize with hard numbers -- generic sentence.
    # (TC / TR / REP / RA are now handled with concrete numbers above.)
    # Overrides trump everything else.
    for m in list(summaries):
        if property_row.get(f"{m}_LOCKED"):
            v = property_row.get(m)
            v_disp = "(no value)" if v is None else v
            lb = property_row.get(f"{m}_LOCKED_BY") or "unknown"
            reason = property_row.get(f"{m}_REASON")
            reason_bit = f' Reason: "{reason}".' if reason else ""
            summaries[m] = {"status": "override",
                            "text": f'MANUALLY OVERRIDDEN to "{v_disp}" by {lb}.{reason_bit}'}

    return summaries


@scorecard_bp.route("/api/property/<int:property_key>/email-scorecard", methods=["POST"])
@login_required
def api_property_email_scorecard(property_key):
    """Send the property's scorecard as an HTML email to the signed-in user.
    Local Windows dev: creates a draft in the user's Outlook client via
    win32com (so they can review before hitting Send). Everywhere else
    (Azure App Service): sends immediately via Graph API sendMail using
    the FabricPipelineApp's already-granted Mail.Send app permission.
    Request body: {"subject": "...", "html_body": "..."}"""
    check = _require_access()
    if check:
        return check
    payload = request.get_json(silent=True) or {}
    subject = (payload.get("subject") or f"Scorecard - Property {property_key}").strip()[:250]
    html_body = payload.get("html_body") or ""
    if not html_body:
        return jsonify({"error": "html_body required"}), 400
    user = session.get("user", {})
    to_email = (user.get("email") or "").strip()
    if not to_email:
        return jsonify({"error": "no email on session"}), 400

    if os.name == "nt":
        try:
            import win32com.client
            outlook = win32com.client.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)
            mail.Subject = subject
            mail.To = to_email
            mail.HTMLBody = html_body
            mail.Display()
            return jsonify({"ok": True, "mode": "local_outlook_draft",
                            "message": f"Draft opened in your Outlook (to {to_email})."})
        except Exception:
            pass

    try:
        _send_via_graph(to_email, subject, html_body)
        return jsonify({"ok": True, "mode": "graph_sent",
                        "message": f"Email sent to {to_email}."})
    except Exception as e:
        return jsonify({"error": f"Send failed: {e}"}), 500


def _send_via_graph(to_email, subject, html_body):
    """POST /users/{email}/sendMail using the FabricPipelineApp client-credentials
    token. The app already has Mail.Send app permission (verified 2026-09-28)."""
    import msal
    import requests as _requests
    env = _get_env()
    tenant_id = env.get("AZURE_TENANT_ID") or env.get("PBI_TENANT_ID")
    client_id = env.get("AZURE_CLIENT_ID") or env.get("GRAPH_CLIENT_ID")
    client_secret = env.get("AZURE_CLIENT_SECRET") or env.get("GRAPH_CLIENT_SECRET")
    if not (tenant_id and client_id and client_secret):
        raise RuntimeError("Graph API credentials missing on this environment")
    app = msal.ConfidentialClientApplication(
        client_id, authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret,
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        raise RuntimeError(f"MSAL token: {result.get('error_description', result.get('error', 'unknown'))}")
    tok = result["access_token"]
    r = _requests.post(
        f"https://graph.microsoft.com/v1.0/users/{to_email}/sendMail",
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
        json={
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": html_body},
                "toRecipients": [{"emailAddress": {"address": to_email}}],
            },
            "saveToSentItems": True,
        },
        timeout=30,
    )
    if r.status_code not in (200, 202):
        raise RuntimeError(f"Graph sendMail HTTP {r.status_code}: {r.text[:300]}")


def _audit_scorecard_change(source_table_key, row_key_dict, field_name, old_value, new_value, action, changed_by, reason=None):
    """Insert a row-level change record into control.SCORECARD_TABLE_MANAGER_AUDIT
    (DB_BI_SUPPORT). Called by the RM-facing write endpoints so field-level
    change history is complete regardless of whether the edit came from the app
    (RM slideout) or the admin Table Manager. Fire-and-forget: any audit failure
    is logged and swallowed -- the user's primary write must not fail because
    the audit database was briefly unreachable."""
    try:
        env = _get_env()
        bi = SafeConnection(env, "DB_BI_SUPPORT", None, direct=True)
        try:
            bi.execute(
                """INSERT INTO control.SCORECARD_TABLE_MANAGER_AUDIT
                    (SOURCE_TABLE_KEY, ROW_KEY, FIELD_NAME, OLD_VALUE, NEW_VALUE,
                     ACTION, CHANGED_BY, CHANGED_AT, REASON)
                   VALUES (?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME(), ?)""",
                (source_table_key,
                 json.dumps(row_key_dict, sort_keys=True),
                 field_name,
                 None if old_value is None else str(old_value),
                 None if new_value is None else str(new_value),
                 action, changed_by, reason))
            bi.commit()
        finally:
            bi.close()
    except Exception as e:
        # Deliberately swallowed -- audit failure must not block user writes.
        print(f"[_audit_scorecard_change] failed for {source_table_key}/{field_name}: {e}")


def _update_own_property(conn, property_key, ay, quarter, admin, email, set_clause, params):
    """UPDATE scoped to the current user's role via _scope_update_where() --
    defense-in-depth (the caller should have already confirmed ownership via
    _scoped_property_row before calling this). `admin` and `email` are kept
    for backward compat but no longer read -- scope now derives from session."""
    sql = f"UPDATE dbo.SCORECARD_CORE SET {set_clause} WHERE PROPERTY_KEY = ? AND AY = ? AND QUARTER = ?"
    where_params = [property_key, ay, quarter]
    extra_sql, extra_params = _scope_update_where()
    sql += extra_sql
    where_params += extra_params
    return conn.execute(sql, params + where_params)


@scorecard_bp.route("/api/overrides/<int:property_key>", methods=["POST"])
@login_required
def api_toggle_override(property_key):
    """Flip a single measure's <measure>_LOCKED bit -- mirrors PDM's
    toggleOverride()/PDM_FIELD_OVERRIDES pattern, but writes directly to
    SCORECARD_CORE's own *_LOCKED companion column instead of a separate
    override table (this table was designed with that convention already
    built in, per Emp_Core). Locking a measure protects it from being
    overwritten the next time NB_LEADERSHIP_SCORECARD_UPDATE runs; it does not by
    itself change the value -- pair with a PATCH to /api/properties/<key>
    to actually set an override value. Optional "reason" text is stored in
    <measure>_REASON (matches the original app's exception-badge concept,
    e.g. "credit of 1 from Director of Operations Support") -- cleared
    when the override is disabled. RMs may override measures within their
    own portfolio (RM_EMAIL match, same scoping as every read endpoint);
    admins/developers may override any property. NOT admin-only
    (2026-09-22: RMs need this too, not just People Ops)."""
    check = _require_access()
    if check:
        return check
    if _is_pm():
        return jsonify({"error": "read-only for Property Managers"}), 403
    user = session.get("user", {})
    payload = request.get_json(force=True) or {}
    field = payload.get("field")
    enabled = bool(payload.get("enabled"))
    reason = (payload.get("reason") or "").strip() or None
    if field not in _MEASURE_KEYS:
        return jsonify({"error": f"unknown field '{field}'"}), 400

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        admin = _is_admin()
        email = _effective_rm_email()
        ay, quarter = _latest_period(conn)
        if ay is None:
            return jsonify({"error": "no data available"}), 404
        owned = _scoped_property_row(conn, property_key, ay, quarter, admin, email,
                                     ["PROPERTY_KEY", f"{field}_LOCKED", f"{field}_LOCKED_BY", f"{field}_REASON"])
        if owned is None:
            return jsonify({"error": "not found or not authorized"}), 404
        old_locked = owned[1]

        locked_by = (user.get("name") or user.get("email") or "") if enabled else None
        reason_val = reason if enabled else None
        cur = _update_own_property(
            conn, property_key, ay, quarter, admin, email,
            f"{field}_LOCKED = ?, {field}_LOCKED_BY = ?, {field}_REASON = ?, DATE_UPDATED = SYSUTCDATETIME(), UPDATED_BY = ?",
            [1 if enabled else 0, locked_by, reason_val, user.get("email", "")])
        conn.commit()
        _audit_scorecard_change(
            source_table_key="scorecard_core",
            row_key_dict={"PROPERTY_KEY": property_key, "AY": ay, "QUARTER": quarter},
            field_name=f"{field}_LOCKED",
            old_value=int(old_locked) if old_locked is not None else 0,
            new_value=1 if enabled else 0,
            action="UPDATE",
            changed_by=user.get("email", ""),
            reason=reason_val,
        )
        return jsonify({"ok": True, "rows_affected": cur.rowcount, "locked_by": locked_by, "reason": reason_val})
    finally:
        conn.close()


@scorecard_bp.route("/api/properties/<int:property_key>", methods=["PATCH"])
@login_required
def api_patch_property(property_key):
    """Set one measure's value directly (the override slideout's edit
    action) and recompute PRERM/LDRTOTAL/MSTOTAL immediately so the grid
    doesn't show stale totals until the next pipeline run. Does NOT itself
    set the <measure>_LOCKED bit -- pair with POST /api/overrides/<key> so
    the edit survives the next pipeline run, exactly like PDM's separate
    override checkbox. EXCEPTION: RMSCORE has no override checkbox in the
    UI at all (2026-09-23) -- it's 100% RM-entered with no pipeline-computed
    baseline to protect against, so every save here always stamps
    RMSCORE_LOCKED_BY ("Updated by X") and sets RMSCORE_LOCKED=1 directly,
    unconditionally. Same RM-or-admin ownership scoping as every other
    endpoint -- NOT admin-only (2026-09-22: RMs need this too)."""
    check = _require_access()
    if check:
        return check
    if _is_pm():
        return jsonify({"error": "read-only for Property Managers"}), 403
    user = session.get("user", {})
    payload = request.get_json(force=True) or {}
    field = next(iter(payload.keys()), None)
    if field not in _MEASURE_KEYS:
        return jsonify({"error": f"unknown field '{field}'"}), 400
    value = payload.get(field)

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        admin = _is_admin()
        email = _effective_rm_email()
        ay, quarter = _latest_period(conn)
        if ay is None:
            return jsonify({"error": "no data available"}), 404
        owned = _scoped_property_row(conn, property_key, ay, quarter, admin, email, ["PROPERTY_KEY", field])
        if owned is None:
            return jsonify({"error": "not found or not authorized"}), 404
        old_value = owned[1]

        updated_by_name = None
        if field == "RMSCORE":
            updated_by_name = user.get("name") or user.get("email") or ""
            set_clause = f"{field} = ?, RMSCORE_LOCKED = 1, RMSCORE_LOCKED_BY = ?, DATE_UPDATED = SYSUTCDATETIME(), UPDATED_BY = ?"
            params = [value, updated_by_name, user.get("email", "")]
        else:
            set_clause = f"{field} = ?, DATE_UPDATED = SYSUTCDATETIME(), UPDATED_BY = ?"
            params = [value, user.get("email", "")]

        cur = _update_own_property(conn, property_key, ay, quarter, admin, email, set_clause, params)
        if cur.rowcount == 0:
            return jsonify({"error": "not found or not authorized"}), 404

        row = _scoped_property_row(conn, property_key, ay, quarter, True, "", _MEASURE_KEYS)
        vals = dict(zip(_MEASURE_KEYS, row))
        prerm = sum(int(vals.get(k) or 0) for k in _OBJECTIVE_KEYS)
        ldrtotal = prerm + int(vals.get("RMSCORE") or 0)
        mstotal = sum(int(vals.get(k) or 0) for k in _MAINT_TOTAL_KEYS)
        conn.execute(
            "UPDATE dbo.SCORECARD_CORE SET PRERM = ?, LDRTOTAL = ?, MSTOTAL = ? WHERE PROPERTY_KEY = ? AND AY = ? AND QUARTER = ?",
            (prerm, ldrtotal, mstotal, property_key, ay, quarter))
        conn.commit()
        _audit_scorecard_change(
            source_table_key="scorecard_core",
            row_key_dict={"PROPERTY_KEY": property_key, "AY": ay, "QUARTER": quarter},
            field_name=field,
            old_value=old_value,
            new_value=value,
            action="UPDATE",
            changed_by=user.get("email", ""),
            reason=("RM slideout save" if field == "RMSCORE" else "RM slideout override edit"),
        )
        return jsonify({"ok": True, "prerm": prerm, "ldrtotal": ldrtotal, "mstotal": mstotal, "overall": ldrtotal + mstotal, "updated_by": updated_by_name})
    finally:
        conn.close()


@scorecard_bp.route("/api/notes/<int:property_key>", methods=["POST"])
@login_required
def api_save_notes(property_key):
    """Set (or clear, via null/empty) the free-text NOTES field -- separate
    from the measure override endpoints since NOTES has no <field>_LOCKED
    bit and its own NOTE_BY/NOTE_AT audit pair (mirrors the original app's
    editedBy/editedAt vs. noteBy/noteAt distinction). Same RM-or-admin
    ownership scoping as every other write endpoint."""
    check = _require_access()
    if check:
        return check
    if _is_pm():
        return jsonify({"error": "read-only for Property Managers"}), 403
    user = session.get("user", {})
    payload = request.get_json(force=True) or {}
    notes = (payload.get("notes") or "").strip() or None

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        admin = _is_admin()
        email = _effective_rm_email()
        ay, quarter = _latest_period(conn)
        if ay is None:
            return jsonify({"error": "no data available"}), 404
        owned = _scoped_property_row(conn, property_key, ay, quarter, admin, email, ["PROPERTY_KEY", "NOTES"])
        if owned is None:
            return jsonify({"error": "not found or not authorized"}), 404
        old_notes = owned[1]

        note_by = (user.get("name") or user.get("email") or "") if notes else None
        cur = _update_own_property(
            conn, property_key, ay, quarter, admin, email,
            "NOTES = ?, NOTE_BY = ?, NOTE_AT = SYSUTCDATETIME(), DATE_UPDATED = SYSUTCDATETIME(), UPDATED_BY = ?",
            [notes, note_by, user.get("email", "")])
        conn.commit()
        _audit_scorecard_change(
            source_table_key="scorecard_core",
            row_key_dict={"PROPERTY_KEY": property_key, "AY": ay, "QUARTER": quarter},
            field_name="NOTES",
            old_value=old_notes,
            new_value=notes,
            action="UPDATE",
            changed_by=user.get("email", ""),
            reason="RM note save",
        )
        return jsonify({"ok": True, "rows_affected": cur.rowcount, "notes": notes, "note_by": note_by})
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────
# Drill-down evidence pages -- per original design ("Clicking a header name
# opens a full table of underlying records for every property"). Reads the
# ORIGINAL WH_PROD2 source tables directly, NOT SCORECARD_CORE -- the
# central table's one-row-per-property-per-quarter grain can't hold this
# row-level detail (per the Phase 1c drill-down-fidelity decision -- see
# repo memory). Read-only, no writes.
# ─────────────────────────────────────────────────────────────────────────
_MEASURE_TO_DRILLDOWN_GROUP = {
    "TC": "TC", "TR": "TR", "PCARD": "PCARD", "RA": "RA",
    "IIPP": "LEO", "LFA": "LEO", "PMLEO": "LEO", "MSLEO": "LEO",
    "REP": "REP", "WO": "WO", "MSWO": "WO",
    "CURB": "RMINSP", "PUBLICAREAS": "RMINSP", "MAINT": "RMINSP", "LOGS": "RMINSP",
    "NOI": "NOI",
}
_DRILLDOWN_LABELS = {
    "TC": "Timecard Approval", "TR": "Training Compliance", "PCARD": "PPV / P-Card",
    "RA": "Risk Assessment", "LEO": "LEO Compliance (IIPP / Lease File Audit / PM &amp; MS LEO)",
    "REP": "Reputation Score", "WO": "Work Orders (PM &amp; Maintenance)",
    "RMINSP": "RM Quarterly Inspection (Curb / Public Areas / Maintenance / Logs)",
    "NOI": "Controllable NOI -- Income Statement by GL",
}
_DRILLDOWN_LINEAGE = {
    "TC": "WH_PROD2.dbo.LS_TIMESHEET (Paycom timecard export, filtered to APRROVAL_TYPE = 'Supervisor')",
    "TR": "WH_PROD2.dbo.GRACEHILL_LOCATION_COMPLIANCE_IMPORT_FACT (Gracehill training compliance import)",
    "PCARD": "WH_PROD2.dbo.LS_PREPAID_VISA (prepaid Visa / P-Card transaction export)",
    "RA": "WH_PROD2.dbo.LS_COMPLIANCE_IMPORT (Risk Assessment action-item import)",
    "LEO": "WH_PROD2.dbo.LEO_COMPLIANCE_EXPORT_FACT (LEO compliance export -- IIPP, Lease File Audit, PM/MS bonus scores)",
    "REP": "WH_PROD2.dbo.REPUTATION_COM_SUMMARY_FACT (Reputation.com summary export, snapshot as of each quarter's closing Friday)",
    "WO": "WH_PROD2.dbo.WORK_ORDER_REQUESTS (work order system export)",
    "RMINSP": "WH_PROD2.dbo.LS_RM_QUARTERLY_INSPECTION_SCORES_FACT (RM quarterly property inspection scores)",
    "NOI": "WH_PROD2.dbo.INCOME_STATEMENT_BY_GL (GL-level income statement, rolled up by ACCOUNT_ROLLUP)",
}


def _quarter_bounds(ay, quarter):
    """(start_date, end_date) for AY/QUARTER -- e.g. (2026,'Q2') -> (2026-04-01, 2026-06-30)."""
    q_num = int(quarter[1])
    start_month = (q_num - 1) * 3 + 1
    start = datetime.date(ay, start_month, 1)
    end_month = start_month + 2
    if end_month == 12:
        end = datetime.date(ay, 12, 31)
    else:
        end = datetime.date(ay, end_month + 1, 1) - datetime.timedelta(days=1)
    return start, end


def _last_friday_on_or_before(d):
    """d.weekday(): Monday=0..Sunday=6, Friday=4 -- matches NB_LEADERSHIP_SCORECARD_UPDATE's helper,
    used here to find the exact 2 closing-Friday snapshots the REP measure compares."""
    offset = (d.weekday() - 4) % 7
    return d - datetime.timedelta(days=offset)


def _norm_entity(x):
    """Matches NB_LEADERSHIP_SCORECARD_UPDATE._consolidate_entity_number's normalization
    (strip trailing .0 from numeric-but-string entity numbers) so DEPARTMENT_CODE
    values line up with SCORECARD_CORE's ENTITY_NUMBER regardless of formatting."""
    try:
        return str(int(float(x)))
    except (TypeError, ValueError):
        return str(x).strip()


def _drilldown_portfolio(conn_app, admin, email, ay, quarter):
    """{PROPERTY_KEY: {'name':.., 'entity':..}} -- scoped to the current user's
    role via _scope_clause(). `admin`/`email` retained for signature compat."""
    where_sql, where_params = _scope_clause("sc")
    rows = conn_app.fetchall(
        f"""SELECT sc.PROPERTY_KEY, sc.PROPERTY_NAME, sc.ENTITY_NUMBER
            FROM dbo.SCORECARD_CORE sc LEFT JOIN dbo.PROPERTY_0 p ON p.PROPERTY_KEY = sc.PROPERTY_KEY
            WHERE sc.FLAG_CURRENT = 1 AND sc.AY = ? AND sc.QUARTER = ? AND {where_sql}""",
        tuple([ay, quarter] + where_params))
    return {r[0]: {"name": r[1], "entity": r[2]} for r in rows}


def _lookup_due_date(date_approved, due_date_calendar):
    """Matches NB_LEADERSHIP_SCORECARD_UPDATE._lookup_due_date exactly."""
    for start, end, due in due_date_calendar:
        if start <= date_approved <= end:
            return due
    return None


def _dd_tc(conn_wh, portfolio, q_start, q_end, measure_code, ref):
    """Violation = the row's approval (per the same NY/Non-NY/West-Coast due-date
    calendar + 10h10m/+2h buffer logic the real TC measure uses) was late.

    FIXED (2026-09-23): a flat TOP 8000 cap ordered by DATE_APPROVED DESC was
    silently dropping most of a quarter's ~56,000 rows (across all properties)
    BEFORE the per-portfolio DEPARTMENT_CODE match happened in Python -- a
    property's late (failing) approvals could land entirely outside that
    top-8000 window while its on-time ones didn't, so no violations ever
    showed up (confirmed live for BROOKS AT STILLWATER: 702 real matching
    rows in the full quarter, only ~101 of which survived the old cap).
    Scopes to the portfolio's actual DEPARTMENT_CODE values FIRST (a cheap
    DISTINCT lookup) so the real per-property row count is always returned,
    no matter how large the whole table's quarter is."""
    entity_to_key = {_norm_entity(v["entity"]): k for k, v in portfolio.items() if v["entity"]}
    if not entity_to_key:
        return ["Property", "Date Approved", "Approval Added", "Payroll Profile"], []
    dept_rows = conn_wh.fetchall("""
        SELECT DISTINCT DEPARTMENT_CODE
        FROM dbo.LS_TIMESHEET
        WHERE APRROVAL_TYPE = 'Supervisor' AND DEPARTMENT_CODE IS NOT NULL
              AND DATE_APPROVED >= ? AND DATE_APPROVED <= ?
    """, (q_start, q_end))
    matching_depts = [d[0] for d in dept_rows if _norm_entity(d[0]) in entity_to_key]
    if not matching_depts:
        return ["Property", "Date Approved", "Approval Added", "Payroll Profile"], []
    placeholders = ",".join("?" for _ in matching_depts)
    rows = conn_wh.fetchall(f"""
        SELECT DEPARTMENT_CODE, DATE_APPROVED, APPROVAL_ADDED, PAYROLL_PROFILE_DESC
        FROM dbo.LS_TIMESHEET
        WHERE APRROVAL_TYPE = 'Supervisor' AND DEPARTMENT_CODE IN ({placeholders})
              AND DATE_APPROVED >= ? AND DATE_APPROVED <= ?
        ORDER BY DATE_APPROVED DESC
    """, matching_depts + [q_start, q_end])
    out = []
    for dept, date_approved, approval_added, payroll in rows:
        pk = entity_to_key.get(_norm_entity(dept))
        if pk is None:
            continue
        violation = False
        entity = _norm_entity(dept)
        if date_approved is not None and approval_added is not None and ref:
            date_approved_d = date_approved.date() if hasattr(date_approved, "date") else date_approved
            is_ny = entity in ref.get("ny_entities", set())
            is_west_coast = entity in ref.get("west_coast_entities", set())
            calendar = ref["ny_due_dates"] if is_ny else ref["nonny_due_dates"]
            due_date = _lookup_due_date(date_approved_d, calendar)
            if due_date is not None:
                due_dt = datetime.datetime.combine(due_date, datetime.time(0, 0)) + datetime.timedelta(hours=10, minutes=10)
                if is_west_coast:
                    due_dt += datetime.timedelta(hours=2)
                approval_added_adj = approval_added + datetime.timedelta(hours=1)
                violation = approval_added_adj > due_dt
        out.append({
            "Property": portfolio[pk]["name"],
            "Date Approved": str(date_approved) if date_approved else None,
            "Approval Added": str(approval_added) if approval_added else None,
            "Payroll Profile": payroll,
            "_fail": violation,
        })
    return ["Property", "Date Approved", "Approval Added", "Payroll Profile"], out


def _dd_tr(conn_wh, portfolio, q_start, q_end, measure_code, ref):
    """Violation = this monthly snapshot alone is below the 94% pass threshold."""
    if not portfolio:
        return [], []
    keys = list(portfolio.keys())
    placeholders = ",".join("?" for _ in keys)
    dk_start = int(q_start.strftime("%Y%m%d"))
    dk_end = int(q_end.strftime("%Y%m%d"))
    rows = conn_wh.fetchall(f"""
        SELECT DISTINCT PROPERTY_KEY, DATE_KEY, COMPLIANCE_PERCENTAGE
        FROM dbo.GRACEHILL_LOCATION_COMPLIANCE_IMPORT_FACT
        WHERE PROPERTY_KEY IN ({placeholders}) AND DATE_KEY >= ? AND DATE_KEY <= ?
    """, keys + [dk_start, dk_end])
    out = [{"Property": portfolio[pk]["name"], "Date": dk, "Compliance %": pct,
            "_fail": pct is not None and float(pct) < 0.94}
           for pk, dk, pct in rows if pk in portfolio]
    return ["Property", "Date", "Compliance %"], out


def _dd_pcard(conn_wh, portfolio, q_start, q_end, measure_code, ref):
    """Violation = every row shown here, by definition -- CONFIRMED (2026-09-22
    stakeholder meeting): ANY reconciliation transaction in the quarter fails
    the measure, so each transaction returned IS the reason for the fail."""
    if not portfolio:
        return [], []
    keys = list(portfolio.keys())
    placeholders = ",".join("?" for _ in keys)
    rows = conn_wh.fetchall(f"""
        SELECT DISTINCT PROPERTY_KEY, DATETIME_RECONCILIATION, LINE_AMOUNT
        FROM dbo.LS_PREPAID_VISA
        WHERE PROPERTY_KEY IN ({placeholders}) AND DATETIME_RECONCILIATION IS NOT NULL
              AND DATETIME_RECONCILIATION >= ? AND DATETIME_RECONCILIATION <= ?
    """, keys + [q_start, q_end])
    out = [{"Property": portfolio[pk]["name"], "Transaction Date": str(txn_date),
            "Amount": float(amount) if amount is not None else None, "_fail": True}
           for pk, txn_date, amount in rows if pk in portfolio]
    return ["Property", "Transaction Date", "Amount"], out


def _dd_ra(conn_wh, portfolio, q_start, q_end, measure_code, ref):
    """Violation = STATUS is not 'Complete' (the only 3 observed values are
    Complete / Incomplete / Cannot Do)."""
    if not portfolio:
        return [], []
    keys = list(portfolio.keys())
    placeholders = ",".join("?" for _ in keys)
    rows = conn_wh.fetchall(f"""
        SELECT DISTINCT TOP 4000 PROPERTY_KEY, [Action Item], STATUS, QUARTER, [Date Completed]
        FROM dbo.LS_COMPLIANCE_IMPORT
        WHERE PROPERTY_KEY IN ({placeholders})
        ORDER BY [Date Completed] DESC
    """, keys)
    out = [{"Property": portfolio[pk]["name"], "Action Item": item, "Status": status,
            "Quarter (as stored)": q, "Date Completed": str(dc) if dc else None,
            "_fail": (status or "").strip().lower() != "complete"}
           for pk, item, status, q, dc in rows if pk in portfolio]
    return ["Property", "Action Item", "Status", "Quarter (as stored)", "Date Completed"], out


_LEO_MEASURE_COLUMN = {"IIPP": "IIPP Complete", "LFA": "Lease File Audit Complete",
                       "PMLEO": "PM LEO Score", "MSLEO": "MS LEO Score"}


def _dd_leo(conn_wh, portfolio, q_start, q_end, measure_code, ref):
    """Violation = the specific measure's own column is 0 on this snapshot --
    CONFIRMED (2026-09-22): any snapshot in the quarter showing 0 fails the
    whole quarter, so every 0 snapshot is itself an offending row."""
    if not portfolio:
        return [], []
    keys = list(portfolio.keys())
    placeholders = ",".join("?" for _ in keys)
    dk_start = int(q_start.strftime("%Y%m%d"))
    dk_end = int(q_end.strftime("%Y%m%d"))
    rows = conn_wh.fetchall(f"""
        SELECT DISTINCT PROPERTY_KEY, DATE_KEY, IIPP_COMPLETE, LEASE_FILE_AUDIT_COMPLETE,
               BONUS_PM_SCORE, BONUS_MS_SCORE, PM_NAME, RM_NAME
        FROM dbo.LEO_COMPLIANCE_EXPORT_FACT
        WHERE PROPERTY_KEY IN ({placeholders}) AND DATE_KEY >= ? AND DATE_KEY <= ?
    """, keys + [dk_start, dk_end])
    watch_col = _LEO_MEASURE_COLUMN.get(measure_code)
    out = []
    for pk, dk, iipp, lfa, pmleo, msleo, pm_name, rm_name in rows:
        if pk not in portfolio:
            continue
        row = {"Property": portfolio[pk]["name"], "Snapshot Date": dk, "IIPP Complete": iipp,
               "Lease File Audit Complete": lfa, "PM LEO Score": pmleo, "MS LEO Score": msleo,
               "PM Name": pm_name, "RM Name": rm_name}
        watch_val = row.get(watch_col) if watch_col else None
        row["_fail"] = watch_val is not None and float(watch_val) == 0
        out.append(row)
    cols = ["Property", "Snapshot Date", "IIPP Complete", "Lease File Audit Complete", "PM LEO Score", "MS LEO Score", "PM Name", "RM Name"]
    return cols, out


def _dd_rep(conn_wh, portfolio, q_start, q_end, measure_code, ref):
    """REP only ever compares 2 exact snapshots (this quarter's closing Friday vs. the
    prior quarter's) -- filtering to just those 2 dates avoids fetching this table's
    genuinely huge per-day density (one property alone returned ~36,000 rows over a
    100-day window in testing; the full portfolio unfiltered was 2.5 MILLION rows).
    Violation = the "This Quarter" row, when its % change vs. the prior snapshot
    is <= 1% (the real pass threshold is > 1% improvement)."""
    if not portfolio:
        return [], []
    keys = list(portfolio.keys())
    placeholders = ",".join("?" for _ in keys)
    prev_q_end = q_start - datetime.timedelta(days=1)
    friday_curr = _last_friday_on_or_before(q_end)
    friday_prev = _last_friday_on_or_before(prev_q_end)
    rows = conn_wh.fetchall(f"""
        SELECT DISTINCT PROPERTY_KEY, DATERANGETO, SCORE
        FROM dbo.REPUTATION_COM_SUMMARY_FACT
        WHERE PROPERTY_KEY IN ({placeholders}) AND SCORE IS NOT NULL
              AND CAST(DATERANGETO AS DATE) IN (?, ?)
        ORDER BY PROPERTY_KEY, DATERANGETO
    """, keys + [friday_curr, friday_prev])
    curr_by_pk, prev_by_pk = {}, {}
    for pk, drt, score in rows:
        if pk not in portfolio or score is None:
            continue
        if drt.date() == friday_curr:
            curr_by_pk[pk] = float(score)
        elif drt.date() == friday_prev:
            prev_by_pk[pk] = float(score)
    out = []
    for pk, drt, score in rows:
        if pk not in portfolio:
            continue
        is_curr = drt.date() == friday_curr
        violation = False
        if is_curr:
            curr, prev = curr_by_pk.get(pk), prev_by_pk.get(pk)
            if curr is not None and prev is not None and prev != 0:
                violation = ((curr - prev) / prev) <= 0.01
        out.append({"Property": portfolio[pk]["name"],
                     "Snapshot": "This Quarter (Closing Friday)" if is_curr else "Prior Quarter (Closing Friday)",
                     "Date Range To": str(drt), "Score": float(score) if score is not None else None,
                     "_fail": violation})
    return ["Property", "Snapshot", "Date Range To", "Score"], out


def _dd_wo(conn_wh, portfolio, q_start, q_end, measure_code, ref):
    """Violation = this individual completed work order alone exceeded the
    1-day open-days pass threshold (a direct proxy for the real month-of-
    monthly-averages calculation)."""
    if not portfolio:
        return [], []
    keys = list(portfolio.keys())
    placeholders = ",".join("?" for _ in keys)
    rows = conn_wh.fetchall(f"""
        SELECT DISTINCT PROPERTY_KEY, COMPLETED_DATE, NET_OPEN_DAY_COUNT
        FROM dbo.WORK_ORDER_REQUESTS
        WHERE PROPERTY_KEY IN ({placeholders}) AND STATUS IN ('Complete', 'COMPLETED')
              AND COMPLETED_DATE IS NOT NULL AND NET_OPEN_DAY_COUNT IS NOT NULL
              AND COMPLETED_DATE >= ? AND COMPLETED_DATE <= ?
    """, keys + [q_start, q_end])
    out = [{"Property": portfolio[pk]["name"], "Completed Date": str(cd),
            "Net Open Days": float(days) if days is not None else None,
            "_fail": days is not None and float(days) > 1}
           for pk, cd, days in rows if pk in portfolio]
    return ["Property", "Completed Date", "Net Open Days"], out


_RMINSP_MEASURE_COLUMN = {"CURB": "Curb Appeal", "PUBLICAREAS": "Public Areas",
                          "MAINT": "Maintenance", "LOGS": "Logs & Binders"}


def _dd_rminsp(conn_wh, portfolio, q_start, q_end, measure_code, ref):
    """Violation = the specific measure's own score is below the 85-point pass threshold."""
    if not portfolio:
        return [], []
    keys = list(portfolio.keys())
    placeholders = ",".join("?" for _ in keys)
    rows = conn_wh.fetchall(f"""
        SELECT DISTINCT PROPERTY_KEY, SCORE_CURB_APPEAL, SCORE_PUBLIC_AREAS_AND_AMENITIES,
               SCORE_MAINTENANCE, SCORE_LOGS_AND_BINDERS
        FROM dbo.LS_RM_QUARTERLY_INSPECTION_SCORES_FACT
        WHERE PROPERTY_KEY IN ({placeholders})
    """, keys)
    watch_col = _RMINSP_MEASURE_COLUMN.get(measure_code)
    out = []
    for pk, curb, pub, maint, logs in rows:
        if pk not in portfolio:
            continue
        row = {"Property": portfolio[pk]["name"], "Curb Appeal": curb, "Public Areas": pub,
               "Maintenance": maint, "Logs & Binders": logs}
        watch_val = row.get(watch_col) if watch_col else None
        row["_fail"] = watch_val is not None and float(watch_val) < 85
        out.append(row)
    return ["Property", "Curb Appeal", "Public Areas", "Maintenance", "Logs & Binders"], out


def _dd_noi(conn_wh, portfolio, q_start, q_end, measure_code, ref):
    """No per-row violation flag -- NOI is manually entered/overridden in the
    slideout (no automated file feed today), so there's no automated rule to
    evaluate against this raw GL detail."""
    if not portfolio:
        return [], []
    keys = list(portfolio.keys())
    placeholders = ",".join("?" for _ in keys)
    periods = []
    y, m = q_start.year, q_start.month
    for _ in range(3):
        periods.append(y * 100 + m)
        m += 1
        if m > 12:
            m = 1
            y += 1
    period_placeholders = ",".join("?" for _ in periods)
    rows = conn_wh.fetchall(f"""
        SELECT DISTINCT PROPERTY_KEY, PERIOD, ACCOUNT_ROLLUP, ACCOUNT_NAME, ACTUALS
        FROM dbo.INCOME_STATEMENT_BY_GL
        WHERE PROPERTY_KEY IN ({placeholders}) AND PERIOD IN ({period_placeholders})
    """, keys + periods)
    out = [{"Property": portfolio[pk]["name"], "Period": period, "Account Rollup": rollup,
            "Account Name": name, "Actuals": float(actuals) if actuals is not None else None,
            "_fail": False}
           for pk, period, rollup, name, actuals in rows if pk in portfolio]
    return ["Property", "Period", "Account Rollup", "Account Name", "Actuals"], out


_DRILLDOWN_QUERY_FUNCS = {
    "TC": _dd_tc, "TR": _dd_tr, "PCARD": _dd_pcard, "RA": _dd_ra,
    "LEO": _dd_leo, "REP": _dd_rep, "WO": _dd_wo, "RMINSP": _dd_rminsp, "NOI": _dd_noi,
}


@scorecard_bp.route("/api/drilldown/<measure_code>")
@login_required
def api_drilldown(measure_code):
    """Per-measure evidence page -- reads the ORIGINAL WH_PROD2 source table
    directly (not SCORECARD_CORE), scoped to the signed-in user's portfolio
    (RM_EMAIL match) unless admin/developer, filtered to the current
    AY/QUARTER shown in the main grid."""
    check = _require_access()
    if check:
        return check
    group = _MEASURE_TO_DRILLDOWN_GROUP.get(measure_code.upper())
    if group is None:
        return jsonify({"error": f"no drill-down defined for '{measure_code}'"}), 400

    env = _get_env()
    conn_app = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        admin = _is_admin()
        email = _effective_rm_email()
        ay, quarter = _latest_period(conn_app)
        if ay is None:
            return jsonify({"error": "no data available"}), 404
        portfolio = _drilldown_portfolio(conn_app, admin, email, ay, quarter)
        ref = {}
        if group == "TC":
            ref["ny_entities"] = {_norm_entity(r[0]) for r in conn_app.fetchall("SELECT ENTITY_NUMBER FROM dbo.SCORECARD_REF_NY_PROPERTIES")}
            ref["west_coast_entities"] = {_norm_entity(r[0]) for r in conn_app.fetchall("SELECT ENTITY_NUMBER FROM dbo.SCORECARD_REF_WEST_COAST_PROPERTIES")}
            ref["ny_due_dates"] = conn_app.fetchall("SELECT START_DATE, END_DATE, DUE_DATE FROM dbo.SCORECARD_REF_NY_DUE_DATES")
            ref["nonny_due_dates"] = conn_app.fetchall("SELECT START_DATE, END_DATE, DUE_DATE FROM dbo.SCORECARD_REF_NONNY_DUE_DATES")
    finally:
        conn_app.close()

    all_property_names = sorted({v["name"] for v in portfolio.values()})
    property_filter = request.args.get("property")
    if property_filter:
        portfolio = {k: v for k, v in portfolio.items() if v["name"] == property_filter}

    q_start, q_end = _quarter_bounds(ay, quarter)
    conn_wh = SafeConnection(env, "WH_PROD2", None)
    try:
        columns, rows = _DRILLDOWN_QUERY_FUNCS[group](conn_wh, portfolio, q_start, q_end, measure_code.upper(), ref)
    finally:
        conn_wh.close()

    rows.sort(key=lambda r: (r.get("Property") or ""))
    total_rows = len(rows)
    row_cap = 2000
    truncated = total_rows > row_cap
    if truncated:
        rows = rows[:row_cap]
    return jsonify({
        "measure": measure_code.upper(),
        "label": _DRILLDOWN_LABELS[group],
        "lineage": _DRILLDOWN_LINEAGE[group],
        "rule": _MEASURE_DEFS_BY_KEY.get(measure_code.upper(), {}).get("blurb", ""),
        "quarter_label": f"{quarter} {ay}",
        "columns": columns,
        "rows": rows,
        "total_rows": total_rows,
        "truncated": truncated,
        "properties": all_property_names,
    })
