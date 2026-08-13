"""Employee Data Manager (EDM) module — manage employee reference data."""
from flask import Blueprint, render_template, session, jsonify, request
from auth import login_required
from modules import MODULES, APP_ID_MAP
import sys
from helpers import load_env, SafeConnection

edm_bp = Blueprint("edm", __name__, url_prefix="/edm")

_env = None


def _get_env():
    global _env
    if _env is None:
        _env = load_env()
    return _env


def _require_access():
    """Check that the current user has access to EDM (app_id=9)."""
    if session.get("is_developer"):
        return None
    user_modules = session.get("user_modules", [])
    for m in user_modules:
        if m["id"] == 9:
            return None
    return jsonify({"error": "unauthorized"}), 403


# ─── PAGE ROUTE ─────────────────────────────────────────────────────────────────

@edm_bp.route("/")
@login_required
def index():
    """Render the EDM page within the shell framework."""
    check = _require_access()
    if check:
        return check
    from config import APP_VERSION
    # Build shell context so the sidebar renders
    user_modules = session.get("user_modules", [])
    allowed_string_ids = set()
    for m in user_modules:
        string_id = APP_ID_MAP.get(m["id"])
        if string_id:
            allowed_string_ids.add(string_id)
    visible = [m for m in MODULES if m["id"] in allowed_string_ids] if user_modules else MODULES
    return render_template("edm.html",
                           modules=visible,
                           active_module="employee_data_manager",
                           user=session.get("user", {}),
                           is_developer=session.get("is_developer", False),
                           is_dev_mode=session.get("is_dev_mode", False),
                           is_impersonating=session.get("is_impersonating", False),
                           impersonating_user=session.get("impersonating_user", None),
                           version=APP_VERSION)


# ─── EMPLOYEES TAB (read-only from EMPLOYEE_F) ─────────────────────────────────

@edm_bp.route("/api/employees/search", methods=["GET"])
@login_required
def search_employees():
    """Search/filter EMPLOYEE_F. Supports q (text search) and filter params."""
    check = _require_access()
    if check:
        return check
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    title_group = request.args.get("title_group", "").strip()
    property_name = request.args.get("property", "").strip()

    env = _get_env()
    conn = SafeConnection(env, "WH_STAGING", None)
    try:
        conditions = ["LOAD_TYPE <> 'PRE-HIRE'"]
        params = []

        if q:
            conditions.append("""(UPPER(NAME_FIRST) LIKE UPPER(?) + '%'
                OR UPPER(NAME_LAST) LIKE UPPER(?) + '%'
                OR UPPER(NAME_FIRST + ' ' + NAME_LAST) LIKE '%' + UPPER(?) + '%'
                OR UPPER(EMAIL) LIKE '%' + UPPER(?) + '%'
                OR UPPER(EMPLOYEE_CODE) = UPPER(?))""")
            params.extend([q, q, q, q, q])

        if status:
            if status == '_ACTIVE':
                conditions.append("STATUS NOT IN ('TERMINATED', 'DECEASED')")
            else:
                conditions.append("STATUS = ?")
                params.append(status)

        if title_group:
            conditions.append("TITLE_GROUP = ?")
            params.append(title_group)

        if property_name:
            conditions.append("PROPERTY_NAME = ?")
            params.append(property_name)

        where = " AND ".join(conditions)
        cur = conn.execute(f"""
            SELECT TOP 1000 e.*,
                leo.TIMEZONE AS LEO_TIMEZONE,
                leo.ROLE AS LEO_ROLE,
                leo.PORTFOLIOS AS LEO_PORTFOLIOS,
                leo.PROPERTIES AS LEO_PROPERTIES,
                leo.REPORT_TO AS LEO_REPORT_TO,
                leo.NOTIFY_NOTE_IMPORTANT AS LEO_NOTIFY_NOTE_IMPORTANT,
                leo.NOTIFY_PROPERTY_CRITICAL AS LEO_NOTIFY_PROPERTY_CRITICAL
            FROM dbo.EMPLOYEE_F e
            LEFT JOIN dbo.LEO_USERS_EXPORT leo ON leo.EMAIL = e.EMAIL
            WHERE {where}
            ORDER BY e.NAME_FIRST, e.NAME_LAST
        """, tuple(params) if params else None)
        columns = [desc[0].lower() for desc in cur.description]
        rows = cur.fetchall()
        result = []
        for r in rows:
            row_dict = {}
            for i, col in enumerate(columns):
                val = r[i]
                # Convert non-serializable types
                if hasattr(val, 'isoformat'):
                    val = val.isoformat()
                row_dict[col] = val
            result.append(row_dict)
        return jsonify(result)
    finally:
        conn.close()


@edm_bp.route("/api/employees/filter-options", methods=["GET"])
@login_required
def employee_filter_options():
    """Get distinct values for filter dropdowns."""
    check = _require_access()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "WH_STAGING", None)
    try:
        statuses = conn.fetchall("""
            SELECT DISTINCT STATUS FROM dbo.EMPLOYEE_F
            WHERE LOAD_TYPE <> 'PRE-HIRE' AND STATUS IS NOT NULL
            ORDER BY STATUS
        """)
        title_groups = conn.fetchall("""
            SELECT DISTINCT TITLE_GROUP FROM dbo.EMPLOYEE_F
            WHERE LOAD_TYPE <> 'PRE-HIRE' AND TITLE_GROUP IS NOT NULL
            ORDER BY TITLE_GROUP
        """)
        properties = conn.fetchall("""
            SELECT DISTINCT PROPERTY_NAME FROM dbo.EMPLOYEE_F
            WHERE LOAD_TYPE <> 'PRE-HIRE' AND PROPERTY_NAME IS NOT NULL
            ORDER BY PROPERTY_NAME
        """)
        return jsonify({
            "statuses": [r[0] for r in statuses],
            "title_groups": [r[0] for r in title_groups],
            "properties": [r[0] for r in properties]
        })
    finally:
        conn.close()


# ─── TITLE ASSIGNMENTS TAB ─────────────────────────────────────────────────────

@edm_bp.route("/api/title-assignments", methods=["GET"])
@login_required
def get_title_assignments():
    """Get all rows from EMP_TITLE_GROUP_MGMT."""
    check = _require_access()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        rows = conn.fetchall("""
            SELECT TITLE, TITLE_GROUP, TITLE_TYPE
            FROM dbo.EMP_TITLE_GROUP_MGMT
            ORDER BY TITLE
        """)
        return jsonify([{
            "title": r[0], "title_group": r[1], "title_type": r[2]
        } for r in rows])
    finally:
        conn.close()


@edm_bp.route("/api/title-assignments", methods=["POST"])
@login_required
def add_title_assignment():
    """Add a new title → title_group mapping."""
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    title = (data.get("title") or "").strip().upper()
    title_group = (data.get("title_group") or "").strip().upper()
    title_type = (data.get("title_type") or "").strip().upper()
    if not title or not title_group:
        return jsonify({"error": "title and title_group required"}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        existing = conn.fetchall(
            "SELECT 1 FROM dbo.EMP_TITLE_GROUP_MGMT WHERE TITLE = ?", (title,))
        if existing:
            return jsonify({"error": "Title already exists"}), 409
        conn.execute("""
            INSERT INTO dbo.EMP_TITLE_GROUP_MGMT (TITLE, TITLE_GROUP, TITLE_TYPE)
            VALUES (?, ?, ?)
        """, (title, title_group, title_type or None))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@edm_bp.route("/api/title-assignments", methods=["PATCH"])
@login_required
def update_title_assignment():
    """Update title_group or title_type for an existing title."""
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    title = (data.get("title") or "").strip()
    field = data.get("field")
    value = (data.get("value") or "").strip().upper()
    if not title or field not in ("title_group", "title_type"):
        return jsonify({"error": "invalid request"}), 400
    col = "TITLE_GROUP" if field == "title_group" else "TITLE_TYPE"
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute(f"UPDATE dbo.EMP_TITLE_GROUP_MGMT SET [{col}] = ? WHERE TITLE = ?",
                     (value or None, title))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@edm_bp.route("/api/title-assignments", methods=["DELETE"])
@login_required
def delete_title_assignment():
    """Delete a title assignment."""
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title required"}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute("DELETE FROM dbo.EMP_TITLE_GROUP_MGMT WHERE TITLE = ?", (title,))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


# ─── ENTRATA MAPPING TAB ───────────────────────────────────────────────────────

@edm_bp.route("/api/entrata-mapping", methods=["GET"])
@login_required
def get_entrata_mapping():
    """Get all rows from EMP_ENTRATA_TITLE_GROUP_MAPPING."""
    check = _require_access()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        rows = conn.fetchall("""
            SELECT TITLE_GROUP, ENTRATA_DEPARTMENT, ENTRATA_PERMISSION_GROUP
            FROM dbo.EMP_ENTRATA_TITLE_GROUP_MAPPING
            ORDER BY TITLE_GROUP
        """)
        return jsonify([{
            "title_group": r[0], "entrata_department": r[1],
            "entrata_permission_group": r[2]
        } for r in rows])
    finally:
        conn.close()


@edm_bp.route("/api/entrata-mapping", methods=["POST"])
@login_required
def add_entrata_mapping():
    """Add a new title_group → entrata mapping."""
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    tg = (data.get("title_group") or "").strip().upper()
    dept = (data.get("entrata_department") or "").strip()
    perm = (data.get("entrata_permission_group") or "").strip()
    if not tg:
        return jsonify({"error": "title_group required"}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        existing = conn.fetchall(
            "SELECT 1 FROM dbo.EMP_ENTRATA_TITLE_GROUP_MAPPING WHERE TITLE_GROUP = ?", (tg,))
        if existing:
            return jsonify({"error": "Title Group already mapped"}), 409
        conn.execute("""
            INSERT INTO dbo.EMP_ENTRATA_TITLE_GROUP_MAPPING
                (TITLE_GROUP, ENTRATA_DEPARTMENT, ENTRATA_PERMISSION_GROUP)
            VALUES (?, ?, ?)
        """, (tg, dept or None, perm or None))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@edm_bp.route("/api/entrata-mapping", methods=["PATCH"])
@login_required
def update_entrata_mapping():
    """Update entrata_department or entrata_permission_group."""
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    tg = (data.get("title_group") or "").strip()
    field = data.get("field")
    value = (data.get("value") or "").strip()
    valid_fields = {"entrata_department": "ENTRATA_DEPARTMENT",
                    "entrata_permission_group": "ENTRATA_PERMISSION_GROUP"}
    if not tg or field not in valid_fields:
        return jsonify({"error": "invalid request"}), 400
    col = valid_fields[field]
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute(f"UPDATE dbo.EMP_ENTRATA_TITLE_GROUP_MAPPING SET [{col}] = ? WHERE TITLE_GROUP = ?",
                     (value or None, tg))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@edm_bp.route("/api/entrata-mapping", methods=["DELETE"])
@login_required
def delete_entrata_mapping():
    """Delete an entrata mapping."""
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    tg = (data.get("title_group") or "").strip()
    if not tg:
        return jsonify({"error": "title_group required"}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute("DELETE FROM dbo.EMP_ENTRATA_TITLE_GROUP_MAPPING WHERE TITLE_GROUP = ?", (tg,))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


# ─── SOFT TERMINATIONS TAB ─────────────────────────────────────────────────────

@edm_bp.route("/api/soft-terminations", methods=["GET"])
@login_required
def get_soft_terminations():
    """Get all soft termination overrides."""
    check = _require_access()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        rows = conn.fetchall("""
            SELECT o.EMPLOYEE_CODE, o.NAME_FIRST, o.NAME_LAST, o.REASON,
                   o.FLAG_SOFT_TERMINATION
            FROM dbo.EMPLOYEE_SOFT_TERMINATION_OVERRIDES o
            ORDER BY o.NAME_LAST, o.NAME_FIRST
        """)
        return jsonify([{
            "employee_code": r[0], "name_first": r[1], "name_last": r[2],
            "reason": r[3],
            "is_active": bool(r[4]) if r[4] is not None else True
        } for r in rows])
    finally:
        conn.close()


@edm_bp.route("/api/soft-terminations", methods=["POST"])
@login_required
def add_soft_termination():
    """Add a new soft termination override."""
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    emp_code = (data.get("employee_code") or "").strip().upper()
    reason = (data.get("reason") or "").strip()
    expires_on = data.get("expires_on") or None  # ISO date string or null
    if not emp_code or not reason:
        return jsonify({"error": "employee_code and reason required"}), 400

    user_email = session.get("user", {}).get("email", "unknown")
    env = _get_env()

    # Look up employee name from EMPLOYEE_F
    conn_wh = SafeConnection(env, "WH_STAGING", None)
    try:
        emp = conn_wh.fetchall("""
            SELECT TOP 1 NAME_FIRST, NAME_LAST
            FROM dbo.EMPLOYEE_F
            WHERE EMPLOYEE_CODE = ? AND LOAD_TYPE <> 'PRE-HIRE'
        """, (emp_code,))
    finally:
        conn_wh.close()

    if not emp:
        return jsonify({"error": f"Employee code {emp_code} not found"}), 404
    name_first, name_last = emp[0]

    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        existing = conn.fetchall(
            "SELECT 1 FROM dbo.EMPLOYEE_SOFT_TERMINATION_OVERRIDES WHERE EMPLOYEE_CODE = ?",
            (emp_code,))
        if existing:
            return jsonify({"error": "Employee already has a soft termination override"}), 409
        conn.execute("""
            INSERT INTO dbo.EMPLOYEE_SOFT_TERMINATION_OVERRIDES
                (EMPLOYEE_CODE, FLAG_SOFT_TERMINATION, NAME_FIRST, NAME_LAST, REASON)
            VALUES (?, 1, ?, ?, ?)
        """, (emp_code, name_first, name_last, reason))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@edm_bp.route("/api/soft-terminations/<emp_code>", methods=["PATCH"])
@login_required
def update_soft_termination(emp_code):
    """Update a soft termination override (reason, expires_on, is_active)."""
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    user_email = session.get("user", {}).get("email", "unknown")
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        sets = []
        params = []
        if "reason" in data:
            sets.append("REASON = ?")
            params.append((data["reason"] or "").strip())
        if "is_active" in data:
            sets.append("FLAG_SOFT_TERMINATION = ?")
            params.append(1 if data["is_active"] else 0)
        if not sets:
            return jsonify({"error": "No fields to update"}), 400
        params.append(emp_code.upper())
        conn.execute(
            f"UPDATE dbo.EMPLOYEE_SOFT_TERMINATION_OVERRIDES SET {', '.join(sets)} WHERE EMPLOYEE_CODE = ?",
            tuple(params))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@edm_bp.route("/api/soft-terminations/<emp_code>", methods=["DELETE"])
@login_required
def delete_soft_termination(emp_code):
    """Permanently remove a soft termination override."""
    check = _require_access()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute(
            "DELETE FROM dbo.EMPLOYEE_SOFT_TERMINATION_OVERRIDES WHERE EMPLOYEE_CODE = ?",
            (emp_code.upper(),))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


# ─── HELPER: Get distinct title groups (for dropdowns) ──────────────────────────

@edm_bp.route("/api/title-groups", methods=["GET"])
@login_required
def get_title_groups():
    """Get distinct title groups from EMP_TITLE_GROUP_MGMT."""
    check = _require_access()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        rows = conn.fetchall("""
            SELECT DISTINCT TITLE_GROUP FROM dbo.EMP_TITLE_GROUP_MGMT
            WHERE TITLE_GROUP IS NOT NULL
            ORDER BY TITLE_GROUP
        """)
        return jsonify([r[0] for r in rows])
    finally:
        conn.close()
