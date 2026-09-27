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
    "RM_EMAIL", "RM_NAME",
    "TC", "TR", "PCARD", "RA", "IIPP", "LFA", "PMLEO", "REP", "WO",
    "RMSCORE", "PRERM", "LDRTOTAL",
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
     "blurb": "RM Quarterly Inspection score for this section. Pass threshold is >=85 points."},
    {"key": "PUBLICAREAS", "label": "Public Areas", "group": "maintenance", "type": "bool",
     "blurb": "RM Quarterly Inspection score for this section. Pass threshold is >=85 points."},
    {"key": "MAINT", "label": "Maintenance", "group": "maintenance", "type": "bool",
     "blurb": "RM Quarterly Inspection score for this section. Pass threshold is >=85 points."},
    {"key": "LOGS", "label": "Safety Logs & Binders", "group": "maintenance", "type": "bool",
     "blurb": "RM Quarterly Inspection score for this section. Pass threshold is >=85 points."},
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


def _is_admin():
    """Check if current user is an admin for Leadership Scorecard (APP_ID=36).
    Same dbo.APP_ADMINS-backed pattern used by every other AppHub module
    (cultivate.py/fasttrack.py/etc.) -- admins see every property; everyone
    else is scoped to their own RM_EMAIL via SCORECARD_CORE."""
    if session.get("is_developer"):
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
    ctx = dict(
        modules=build_nav_modules(),
        active_module="leadership_scorecard",
        user=user,
        is_developer=is_dev,
        is_dev_mode=session.get("is_dev_mode", False),
        rm_profile=rm_profile,
        is_admin=_is_admin(),
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
_SCORECARD_NOTEBOOK_NAME = "NB_SCORECARD_PIPELINE"
_scorecard_notebook_id_cache = {"id": None}


def _resolve_scorecard_notebook_id(env):
    """Look up NB_SCORECARD_PIPELINE's item id in the ETL workspace, cached."""
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
    """Trigger a Fabric run of NB_SCORECARD_PIPELINE. Returns the monitor URL
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

    conn = SafeConnection(env, cfg["db"], None, direct=cfg.get("direct", False))
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
        user = session.get("user", {})
        email = (user.get("email") or "").lower()

        latest = conn.fetchall("""
            SELECT TOP 1 AY, QUARTER FROM dbo.SCORECARD_CORE
            WHERE FLAG_CURRENT = 1
            ORDER BY AY DESC, CAST(SUBSTRING(QUARTER, 2, 1) AS INT) DESC
        """)
        if not latest:
            return jsonify({"ay": None, "quarter": None, "quarter_label": None, "is_admin": admin, "rows": [], "prior_quarter": None})
        ay, quarter = latest[0][0], latest[0][1]

        all_cols = _GRID_COLUMNS + _LOCK_COLUMNS + _LOCK_BY_COLUMNS + _REASON_COLUMNS
        cols_sql = ", ".join(all_cols)
        if admin:
            rows = conn.fetchall(f"""
                SELECT {cols_sql} FROM dbo.SCORECARD_CORE
                WHERE FLAG_CURRENT = 1 AND AY = ? AND QUARTER = ?
                ORDER BY PROPERTY_NAME
            """, (ay, quarter))
        else:
            rows = conn.fetchall(f"""
                SELECT {cols_sql} FROM dbo.SCORECARD_CORE
                WHERE FLAG_CURRENT = 1 AND AY = ? AND QUARTER = ? AND LOWER(RM_EMAIL) = ?
                ORDER BY PROPERTY_NAME
            """, (ay, quarter, email))
        data = [dict(zip(all_cols, r)) for r in rows]
        for r in data:
            r["OVERALL"] = (r["LDRTOTAL"] or 0) + (r["MSTOTAL"] or 0)

        prior_payload = None
        if request.args.get("prior") == "1":
            q_num = int(quarter[1])
            prev_ay, prev_q = (ay - 1, "Q4") if q_num == 1 else (ay, f"Q{q_num - 1}")
            prior_cols = ["PROPERTY_KEY", "PRERM", "LDRTOTAL", "MSTOTAL"]
            prior_cols_sql = ", ".join(prior_cols)
            if admin:
                prior_rows = conn.fetchall(f"""
                    SELECT {prior_cols_sql} FROM dbo.SCORECARD_CORE
                    WHERE FLAG_CURRENT = 1 AND AY = ? AND QUARTER = ?
                """, (prev_ay, prev_q))
            else:
                prior_rows = conn.fetchall(f"""
                    SELECT {prior_cols_sql} FROM dbo.SCORECARD_CORE
                    WHERE FLAG_CURRENT = 1 AND AY = ? AND QUARTER = ? AND LOWER(RM_EMAIL) = ?
                """, (prev_ay, prev_q, email))
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
    cols_sql = ", ".join(cols)
    if admin:
        rows = conn.fetchall(
            f"SELECT {cols_sql} FROM dbo.SCORECARD_CORE WHERE PROPERTY_KEY = ? AND AY = ? AND QUARTER = ? AND FLAG_CURRENT = 1",
            (property_key, ay, quarter))
    else:
        rows = conn.fetchall(
            f"SELECT {cols_sql} FROM dbo.SCORECARD_CORE WHERE PROPERTY_KEY = ? AND AY = ? AND QUARTER = ? AND FLAG_CURRENT = 1 AND LOWER(RM_EMAIL) = ?",
            (property_key, ay, quarter, email))
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
        user = session.get("user", {})
        email = (user.get("email") or "").lower()
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
        data["can_edit"] = True
        return jsonify(data)
    finally:
        conn.close()


def _update_own_property(conn, property_key, ay, quarter, admin, email, set_clause, params):
    """UPDATE scoped to admin-or-owning-RM -- same RM_EMAIL-match rule every
    read endpoint already enforces, applied here as defense-in-depth (the
    caller should have already confirmed ownership via _scoped_property_row
    before calling this)."""
    sql = f"UPDATE dbo.SCORECARD_CORE SET {set_clause} WHERE PROPERTY_KEY = ? AND AY = ? AND QUARTER = ?"
    where_params = [property_key, ay, quarter]
    if not admin:
        sql += " AND LOWER(RM_EMAIL) = ?"
        where_params.append(email)
    return conn.execute(sql, params + where_params)


@scorecard_bp.route("/api/overrides/<int:property_key>", methods=["POST"])
@login_required
def api_toggle_override(property_key):
    """Flip a single measure's <measure>_LOCKED bit -- mirrors PDM's
    toggleOverride()/PDM_FIELD_OVERRIDES pattern, but writes directly to
    SCORECARD_CORE's own *_LOCKED companion column instead of a separate
    override table (this table was designed with that convention already
    built in, per Emp_Core). Locking a measure protects it from being
    overwritten the next time NB_SCORECARD_PIPELINE runs; it does not by
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
        user = session.get("user", {})
        email = (user.get("email") or "").lower()
        ay, quarter = _latest_period(conn)
        if ay is None:
            return jsonify({"error": "no data available"}), 404
        owned = _scoped_property_row(conn, property_key, ay, quarter, admin, email, ["PROPERTY_KEY"])
        if owned is None:
            return jsonify({"error": "not found or not authorized"}), 404

        locked_by = (user.get("name") or user.get("email") or "") if enabled else None
        reason_val = reason if enabled else None
        cur = _update_own_property(
            conn, property_key, ay, quarter, admin, email,
            f"{field}_LOCKED = ?, {field}_LOCKED_BY = ?, {field}_REASON = ?, DATE_UPDATED = SYSUTCDATETIME(), UPDATED_BY = ?",
            [1 if enabled else 0, locked_by, reason_val, user.get("email", "")])
        conn.commit()
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
    payload = request.get_json(force=True) or {}
    field = next(iter(payload.keys()), None)
    if field not in _MEASURE_KEYS:
        return jsonify({"error": f"unknown field '{field}'"}), 400
    value = payload.get(field)

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        admin = _is_admin()
        user = session.get("user", {})
        email = (user.get("email") or "").lower()
        ay, quarter = _latest_period(conn)
        if ay is None:
            return jsonify({"error": "no data available"}), 404
        owned = _scoped_property_row(conn, property_key, ay, quarter, admin, email, ["PROPERTY_KEY"])
        if owned is None:
            return jsonify({"error": "not found or not authorized"}), 404

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
    payload = request.get_json(force=True) or {}
    notes = (payload.get("notes") or "").strip() or None

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        admin = _is_admin()
        user = session.get("user", {})
        email = (user.get("email") or "").lower()
        ay, quarter = _latest_period(conn)
        if ay is None:
            return jsonify({"error": "no data available"}), 404
        owned = _scoped_property_row(conn, property_key, ay, quarter, admin, email, ["PROPERTY_KEY"])
        if owned is None:
            return jsonify({"error": "not found or not authorized"}), 404

        note_by = (user.get("name") or user.get("email") or "") if notes else None
        cur = _update_own_property(
            conn, property_key, ay, quarter, admin, email,
            "NOTES = ?, NOTE_BY = ?, NOTE_AT = SYSUTCDATETIME(), DATE_UPDATED = SYSUTCDATETIME(), UPDATED_BY = ?",
            [notes, note_by, user.get("email", "")])
        conn.commit()
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
    """d.weekday(): Monday=0..Sunday=6, Friday=4 -- matches NB_SCORECARD_PIPELINE's helper,
    used here to find the exact 2 closing-Friday snapshots the REP measure compares."""
    offset = (d.weekday() - 4) % 7
    return d - datetime.timedelta(days=offset)


def _norm_entity(x):
    """Matches NB_SCORECARD_PIPELINE._consolidate_entity_number's normalization
    (strip trailing .0 from numeric-but-string entity numbers) so DEPARTMENT_CODE
    values line up with SCORECARD_CORE's ENTITY_NUMBER regardless of formatting."""
    try:
        return str(int(float(x)))
    except (TypeError, ValueError):
        return str(x).strip()


def _drilldown_portfolio(conn_app, admin, email, ay, quarter):
    """{PROPERTY_KEY: {'name':.., 'entity':..}} -- same RM-or-admin scoping as the main grid."""
    cols_sql = "PROPERTY_KEY, PROPERTY_NAME, ENTITY_NUMBER"
    if admin:
        rows = conn_app.fetchall(
            f"SELECT {cols_sql} FROM dbo.SCORECARD_CORE WHERE FLAG_CURRENT = 1 AND AY = ? AND QUARTER = ?",
            (ay, quarter))
    else:
        rows = conn_app.fetchall(
            f"SELECT {cols_sql} FROM dbo.SCORECARD_CORE WHERE FLAG_CURRENT = 1 AND AY = ? AND QUARTER = ? AND LOWER(RM_EMAIL) = ?",
            (ay, quarter, email))
    return {r[0]: {"name": r[1], "entity": r[2]} for r in rows}


def _lookup_due_date(date_approved, due_date_calendar):
    """Matches NB_SCORECARD_PIPELINE._lookup_due_date exactly."""
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
        user = session.get("user", {})
        email = (user.get("email") or "").lower()
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
