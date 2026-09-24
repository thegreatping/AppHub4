"""Leadership & Maintenance Scorecard module -- quarterly RM bonus scoring.

Data source : WH_PROD2 (LS_TIMESHEET, LS_TRAINING, LS_PREPAID_VISA, LS_RISK_ASSESSMENT,
              LS_IIPP, LS_LEASE_FILE_AUDIT, LEO_COMPLIANCE_EXPORT_FACT,
              REPUTATION_COM_SUMMARY_FACT, LS_RM_QUARTERLY_INSPECTION_SCORES_FACT,
              WORK_ORDER_REQUESTS, INCOME_STATEMENT_BY_GL)
Identity    : DB_APP_SUPPORT.dbo.Emp_Core (NOT EMPLOYEE_F -- EMPLOYEE_F is being retired)
APP_ID      : 36
"""
from flask import Blueprint, render_template, session, jsonify, request
from auth import login_required
from nav import build_nav_modules
from helpers import load_env, SafeConnection
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
    "NOTES",
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
