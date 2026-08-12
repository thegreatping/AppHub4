"""AppHub Maintenance module — admin panel for managing modules and audience."""
from flask import Blueprint, render_template, session, jsonify, request
from auth import login_required
from modules import MODULES, APP_ID_MAP
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

maintenance_bp = Blueprint("maintenance", __name__, url_prefix="/maintenance")

_env = None


def _get_env():
    global _env
    if _env is None:
        _env = load_env()
    return _env


def _require_admin():
    """Check that the current user has admin/developer access to maintenance."""
    if session.get("is_developer"):
        return None  # Developers always have access
    user_modules = session.get("user_modules", [])
    for m in user_modules:
        if m["id"] == 14 and m.get("access") == "admin":
            return None
    return jsonify({"error": "unauthorized"}), 403


# ─── PAGE ROUTE ─────────────────────────────────────────────────────────────────

@maintenance_bp.route("/")
@login_required
def index():
    """Render the maintenance admin panel within the shell framework."""
    check = _require_admin()
    if check:
        return check
    from config import APP_VERSION
    user_modules = session.get("user_modules", [])
    allowed_string_ids = set()
    for m in user_modules:
        string_id = APP_ID_MAP.get(m["id"])
        if string_id:
            allowed_string_ids.add(string_id)
    visible = [m for m in MODULES if m["id"] in allowed_string_ids] if user_modules else MODULES
    return render_template("maintenance.html",
                           modules=visible,
                           active_module="apphub_maintenance",
                           user=session.get("user", {}),
                           is_developer=session.get("is_developer", False),
                           is_dev_mode=session.get("is_dev_mode", False),
                           is_impersonating=session.get("is_impersonating", False),
                           impersonating_user=session.get("impersonating_user", None),
                           version=APP_VERSION)


# ─── MODULE REGISTRY API ────────────────────────────────────────────────────────

@maintenance_bp.route("/api/modules", methods=["GET"])
@login_required
def get_modules():
    """Get all modules from APP_LIST."""
    check = _require_admin()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        rows = conn.fetchall("""
            SELECT App_ID, App_Name, App_Level, App_Security_Level, Flag_Active
            FROM dbo.APP_LIST ORDER BY App_Name
        """)
        return jsonify([{
            "id": r[0], "name": r[1], "level": r[2],
            "security_level": r[3], "active": r[4]
        } for r in rows])
    finally:
        conn.close()


@maintenance_bp.route("/api/modules/<int:app_id>", methods=["PATCH"])
@login_required
def update_module(app_id):
    """Update a module's name or active status."""
    check = _require_admin()
    if check:
        return check
    data = request.get_json()
    allowed_fields = {"name": "App_Name", "active": "Flag_Active"}
    updates = []
    params = []
    for key, col in allowed_fields.items():
        if key in data:
            updates.append(f"{col} = ?")
            params.append(data[key])
    if not updates:
        return jsonify({"error": "no valid fields"}), 400
    params.append(app_id)
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute(
            f"UPDATE dbo.APP_LIST SET {', '.join(updates)} WHERE App_ID = ?",
            tuple(params)
        )
        return jsonify({"success": True})
    finally:
        conn.close()


# ─── AUDIENCE MANAGER API ────────────────────────────────────────────────────────

@maintenance_bp.route("/api/audience/<int:module_id>", methods=["GET"])
@login_required
def get_audience(module_id):
    """Get all audience grants for a specific module."""
    check = _require_admin()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        rows = conn.fetchall("""
            SELECT ID, MODULE_ID, GRANT_TYPE, GRANT_VALUE, ACCESS_LEVEL
            FROM dbo.MODULE_AUDIENCE
            WHERE MODULE_ID = ?
            ORDER BY GRANT_TYPE, GRANT_VALUE
        """, (module_id,))
        grants = [{
            "id": r[0], "module_id": r[1], "grant_type": r[2],
            "grant_value": r[3], "access_level": r[4], "display_name": None
        } for r in rows]
    finally:
        conn.close()

    # Resolve names for individual/exclude grants (emails)
    emails = [g["grant_value"] for g in grants if g["grant_type"] in ("individual", "exclude")]
    if emails:
        conn2 = SafeConnection(env, "WH_STAGING", None)
        try:
            placeholders = ",".join(["?" for _ in emails])
            name_rows = conn2.fetchall(f"""
                SELECT LOWER(EMAIL), NAME_FULL FROM dbo.EMPLOYEE_F
                WHERE LOWER(EMAIL) IN ({placeholders})
            """, tuple(e.lower() for e in emails))
            name_map = {r[0]: r[1] for r in name_rows}
            for g in grants:
                if g["grant_type"] in ("individual", "exclude"):
                    g["display_name"] = name_map.get(g["grant_value"].lower())
        finally:
            conn2.close()

    return jsonify(grants)


@maintenance_bp.route("/api/audience", methods=["POST"])
@login_required
def add_audience_grant():
    """Add a new audience grant."""
    check = _require_admin()
    if check:
        return check
    data = request.get_json()
    module_id = data.get("module_id")
    grant_type = data.get("grant_type", "").strip().lower()
    grant_value = data.get("grant_value", "").strip()
    access_level = data.get("access_level", "user").strip().lower()

    if not module_id or not grant_type or not grant_value:
        return jsonify({"error": "module_id, grant_type, and grant_value required"}), 400
    if grant_type not in ("title_group", "individual", "title_prefix", "developer"):
        return jsonify({"error": "invalid grant_type"}), 400
    if access_level not in ("user", "admin"):
        return jsonify({"error": "invalid access_level"}), 400

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        # Check for duplicate
        existing = conn.fetchall("""
            SELECT 1 FROM dbo.MODULE_AUDIENCE
            WHERE MODULE_ID = ? AND GRANT_TYPE = ? AND GRANT_VALUE = ?
        """, (module_id, grant_type, grant_value))
        if existing:
            return jsonify({"error": "grant already exists"}), 409

        # Get next ID
        max_id = conn.fetchall("SELECT ISNULL(MAX(ID), 0) FROM dbo.MODULE_AUDIENCE")
        new_id = max_id[0][0] + 1

        conn.execute("""
            INSERT INTO dbo.MODULE_AUDIENCE (ID, MODULE_ID, GRANT_TYPE, GRANT_VALUE, ACCESS_LEVEL)
            VALUES (?, ?, ?, ?, ?)
        """, (new_id, module_id, grant_type, grant_value, access_level))
        return jsonify({"success": True, "id": new_id})
    finally:
        conn.close()


@maintenance_bp.route("/api/audience/<int:grant_id>", methods=["DELETE"])
@login_required
def delete_audience_grant(grant_id):
    """Delete an audience grant by ID."""
    check = _require_admin()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute("DELETE FROM dbo.MODULE_AUDIENCE WHERE ID = ?", (grant_id,))
        return jsonify({"success": True})
    finally:
        conn.close()


@maintenance_bp.route("/api/audience/<int:grant_id>", methods=["PATCH"])
@login_required
def update_audience_grant(grant_id):
    """Update an audience grant's access level."""
    check = _require_admin()
    if check:
        return check
    data = request.get_json()
    access_level = data.get("access_level", "").strip().lower()
    if access_level not in ("user", "admin"):
        return jsonify({"error": "invalid access_level"}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute(
            "UPDATE dbo.MODULE_AUDIENCE SET ACCESS_LEVEL = ? WHERE ID = ?",
            (access_level, grant_id)
        )
        return jsonify({"success": True})
    finally:
        conn.close()


# ─── USER LOOKUP API ─────────────────────────────────────────────────────────────
@maintenance_bp.route("/api/user-search", methods=["GET"])
@login_required
def user_search():
    """Search active employees by name. Returns up to 20 matches."""
    check = _require_admin()
    if check:
        return check
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    env = _get_env()
    conn = SafeConnection(env, "WH_STAGING", None)
    try:
        rows = conn.fetchall("""
            SELECT TOP 20 NAME_FULL, EMAIL, TITLE_GROUP, PROPERTY_NAME
            FROM dbo.EMPLOYEE_F
            WHERE FLAG_ACTIVE = 1 AND UPPER(NAME_FULL) LIKE UPPER(?)
            ORDER BY NAME_FULL
        """, (f"%{q}%",))
        return jsonify([{"name": r[0], "email": r[1], "title_group": r[2] or "", "property": r[3] or ""} for r in rows])
    finally:
        conn.close()

@maintenance_bp.route("/api/user-lookup", methods=["GET"])
@login_required
def user_lookup():
    """Look up what modules a specific user would see."""
    check = _require_admin()
    if check:
        return check
    email = request.args.get("email", "").strip().lower()
    if not email:
        return jsonify({"error": "email required"}), 400

    from security import get_employee_info, resolve_access
    emp = get_employee_info(email)
    if not emp:
        return jsonify({"error": "employee not found"}), 404

    access = resolve_access(emp["title_group"], email)

    # Get individual grants and exclusions for this user
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        ind_rows = conn.fetchall("""
            SELECT MODULE_ID FROM dbo.MODULE_AUDIENCE
            WHERE GRANT_TYPE = 'individual' AND LOWER(GRANT_VALUE) = ?
        """, (email,))
        individual_module_ids = [r[0] for r in ind_rows]

        excl_rows = conn.fetchall("""
            SELECT MODULE_ID FROM dbo.MODULE_AUDIENCE
            WHERE GRANT_TYPE = 'exclude' AND LOWER(GRANT_VALUE) = ?
        """, (email,))
        excluded_module_ids = [r[0] for r in excl_rows]
    finally:
        conn.close()

    return jsonify({
        "employee": emp,
        "modules": access["modules"],
        "individual_grants": individual_module_ids,
        "excluded_modules": excluded_module_ids,
        "is_developer": access["is_developer"],
        "module_count": len(access["modules"]),
    })


# ─── USAGE LOG API ──────────────────────────────────────────────────────────────

@maintenance_bp.route("/api/usage-log", methods=["GET"])
@login_required
def get_usage_log():
    """Return recent usage log entries (developer/admin only)."""
    check = _require_admin()
    if check:
        return check

    days   = min(int(request.args.get("days", 7)), 90)   # cap at 90 days
    module = request.args.get("module", "").strip()
    email  = request.args.get("email", "").strip().lower()

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        # Exclude browser/file noise (favicon.ico, robots.txt, etc.)
        conditions = [
            "logged_at >= DATEADD(day, ?, GETUTCDATE())",
            "module_id NOT LIKE '%.%'",
        ]
        params = [-days]
        if module:
            conditions.append("module_id = ?")
            params.append(module)
        if email:
            conditions.append("LOWER(user_email) = ?")
            params.append(email)

        where = " AND ".join(conditions)
        cur = conn.execute(f"""
            SELECT TOP 2000
                log_id,
                CONVERT(varchar(19),
                    DATEADD(hour, -4, logged_at), 120) AS logged_et,
                user_email, user_name, module_id, route,
                http_method, status_code
            FROM dbo.APPHUB_USAGE_LOG
            WHERE {where}
            ORDER BY log_id DESC
        """, params)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

        # Summary counts
        summary_cur = conn.execute(f"""
            SELECT module_id, COUNT(*) AS hits, COUNT(DISTINCT user_email) AS users
            FROM dbo.APPHUB_USAGE_LOG
            WHERE {where}
            GROUP BY module_id
            ORDER BY hits DESC
        """, params)
        summary = [{"module": r[0], "hits": r[1], "users": r[2]}
                   for r in summary_cur.fetchall()]

        # Daily breakdown (for chart) — group by calendar day in ET (UTC-4 approx)
        daily_cur = conn.execute(f"""
            SELECT
                CONVERT(varchar(10), DATEADD(hour, -4, logged_at), 120) AS day_et,
                COUNT(*) AS hits,
                COUNT(DISTINCT user_email) AS users
            FROM dbo.APPHUB_USAGE_LOG
            WHERE {where}
            GROUP BY CONVERT(varchar(10), DATEADD(hour, -4, logged_at), 120)
            ORDER BY day_et
        """, params)
        daily = [{"day": r[0], "hits": r[1], "users": r[2]}
                 for r in daily_cur.fetchall()]

        # Top users
        users_cur = conn.execute(f"""
            SELECT TOP 10
                user_name, user_email, COUNT(*) AS hits
            FROM dbo.APPHUB_USAGE_LOG
            WHERE {where}
            GROUP BY user_name, user_email
            ORDER BY hits DESC
        """, params)
        top_users = [{"name": r[0], "email": r[1], "hits": r[2]}
                     for r in users_cur.fetchall()]

        return jsonify({"rows": rows, "summary": summary, "daily": daily,
                        "top_users": top_users, "total": len(rows)})
    finally:
        conn.close()


@maintenance_bp.route("/api/user-grant", methods=["POST", "DELETE"])
@login_required
def user_grant():
    """Add or remove an individual grant for a specific user+module."""
    check = _require_admin()
    if check:
        return check
    data = request.get_json()
    email = (data.get("email") or "").strip().lower()
    module_id = data.get("module_id")
    action = data.get("action", "grant")  # "grant" or "exclude"
    if not email or module_id is None:
        return jsonify({"error": "email and module_id required"}), 400

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        if request.method == "POST":
            grant_type = "exclude" if action == "exclude" else "individual"
            # Check for duplicate
            existing = conn.fetchall("""
                SELECT 1 FROM dbo.MODULE_AUDIENCE
                WHERE MODULE_ID = ? AND GRANT_TYPE = ? AND LOWER(GRANT_VALUE) = ?
            """, (module_id, grant_type, email))
            if existing:
                return jsonify({"error": "Already exists"}), 409
            conn.execute("""
                INSERT INTO dbo.MODULE_AUDIENCE (MODULE_ID, GRANT_TYPE, GRANT_VALUE, ACCESS_LEVEL)
                VALUES (?, ?, ?, 'user')
            """, (module_id, grant_type, email))
            conn.commit()
            return jsonify({"ok": True})
        else:
            # DELETE - remove grant by type
            grant_type = "exclude" if action == "exclude" else "individual"
            conn.execute("""
                DELETE FROM dbo.MODULE_AUDIENCE
                WHERE MODULE_ID = ? AND GRANT_TYPE = ? AND LOWER(GRANT_VALUE) = ?
            """, (module_id, grant_type, email))
            conn.commit()
            return jsonify({"ok": True})
    finally:
        conn.close()


# ─── TITLE GROUPS REFERENCE ─────────────────────────────────────────────────────

@maintenance_bp.route("/api/title-groups", methods=["GET"])
@login_required
def get_title_groups():
    """Get all title groups for dropdown reference."""
    check = _require_admin()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "WH_STAGING", None)
    try:
        rows = conn.fetchall("""
            SELECT DISTINCT TITLE_GROUP
            FROM dbo.EMPLOYEE_F
            WHERE FLAG_ACTIVE = 1 AND TITLE_GROUP IS NOT NULL AND TITLE_GROUP != ''
            ORDER BY TITLE_GROUP
        """)
        return jsonify([r[0] for r in rows])
    finally:
        conn.close()


# ─── DIAGNOSTICS API ─────────────────────────────────────────────────────────────

@maintenance_bp.route("/api/diagnostics")
@login_required
def api_diagnostics():
    """
    On-demand connection health check for all data sources.
    Tests each connection, measures round-trip latency, and returns key metrics.
    Never runs in the background — only executes when explicitly called.
    """
    check = _require_admin()
    if check:
        return check

    import time

    env = _get_env()
    results = []

    # ── Data source definitions ─────────────────────────────────────────────────
    SOURCES = [
        {
            "id": "DB_APP_SUPPORT",
            "label": "DB App Support (Direct)",
            "kwargs": {"direct": True},
            "probe_sql": "SELECT COUNT(*) FROM dbo.APP_LIST",
            "probe_label": "APP_LIST row count",
            "detail_sql": (
                "SELECT "
                "  (SELECT COUNT(*) FROM dbo.APP_LIST)          AS module_count, "
                "  (SELECT COUNT(*) FROM dbo.APP_ADMINS)        AS admin_count, "
                "  (SELECT COUNT(*) FROM dbo.MODULE_AUDIENCE)   AS audience_count, "
                "  (SELECT COUNT(*) FROM dbo.SAM_GL_WORKTABLE)  AS sam_rows, "
                "  (SELECT COUNT(*) FROM dbo.PROPERTY_0 WHERE FLAG_REPORTABLE=1 AND FLAG_DISPOSITIONED=0) AS active_properties"
            ),
            "detail_cols": ["module_count","admin_count","audience_count","sam_rows","active_properties"],
        },
        {
            "id": "WH_STAGING",
            "label": "WH Staging (Tunnel)",
            "kwargs": {},
            "probe_sql": "SELECT COUNT(*) FROM dbo.EMPLOYEE_F WHERE FLAG_ACTIVE=1",
            "probe_label": "Active employee count",
            "detail_sql": (
                "SELECT "
                "  (SELECT COUNT(*) FROM dbo.EMPLOYEE_F WHERE FLAG_ACTIVE=1)   AS active_employees, "
                "  (SELECT COUNT(*) FROM dbo.EMPLOYEE_F)                        AS total_employees, "
                "  (SELECT COUNT(DISTINCT PROPERTY_KEY) FROM dbo.EMPLOYEE_F WHERE FLAG_ACTIVE=1) AS properties_with_staff"
            ),
            "detail_cols": ["active_employees","total_employees","properties_with_staff"],
        },
    ]

    for src in SOURCES:
        entry = {
            "id":    src["id"],
            "label": src["label"],
            "status": "ok",
            "latency_ms": None,
            "probe_label": src["probe_label"],
            "probe_value": None,
            "metrics": {},
            "error": None,
        }
        t0 = time.perf_counter()
        try:
            conn = SafeConnection(env, src["id"], None, **src["kwargs"])
            try:
                # Probe query — measures connection + one-row latency
                probe_rows = conn.fetchall(src["probe_sql"])
                entry["latency_ms"] = round((time.perf_counter() - t0) * 1000)
                entry["probe_value"] = probe_rows[0][0] if probe_rows else None

                # Detail metrics
                detail_rows = conn.fetchall(src["detail_sql"])
                if detail_rows:
                    for col, val in zip(src["detail_cols"], detail_rows[0]):
                        entry["metrics"][col] = val
            finally:
                conn.close()
        except Exception as exc:
            entry["status"] = "error"
            entry["error"]  = str(exc)
            entry["latency_ms"] = round((time.perf_counter() - t0) * 1000)

        results.append(entry)

    # ── Flask app runtime metrics ───────────────────────────────────────────────
    import os, sys as _sys
    runtime = {
        "python_version": _sys.version.split()[0],
        "pid": os.getpid(),
        "module_count": len(MODULES),
        "env_keys": sorted([k for k in env.keys()]) if isinstance(env, dict) else [],
    }

    return jsonify({"sources": results, "runtime": runtime})

