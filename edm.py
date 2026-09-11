"""Employee Data Manager (EDM) module — manage employee reference data."""
from flask import Blueprint, render_template, session, jsonify, request
from auth import login_required
from modules import MODULES, APP_ID_MAP
from nav import build_nav_modules
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
    visible = build_nav_modules()
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


# ─── LEO MAPPING TAB ────────────────────────────────────────────────────────────

@edm_bp.route("/api/leo-mapping", methods=["GET"])
@login_required
def get_leo_mapping():
    """Get all rows from LEO_TITLE_PAYCOM_MAP."""
    check = _require_access()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        rows = conn.fetchall("""
            SELECT MAP_ID, TITLE_PAYCOM, LEO_ROLE_NAME, MATCH_TYPE, PRIORITY, ENABLED, NOTES
            FROM dbo.LEO_TITLE_PAYCOM_MAP
            ORDER BY TITLE_PAYCOM
        """)
        return jsonify([{
            "map_id": r[0], "title_paycom": r[1], "leo_role_name": r[2],
            "match_type": r[3], "priority": r[4], "enabled": bool(r[5]), "notes": r[6]
        } for r in rows])
    finally:
        conn.close()


@edm_bp.route("/api/leo-roles", methods=["GET"])
@login_required
def get_leo_roles():
    """Get distinct LEO role names for the mapping datalist."""
    check = _require_access()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        rows = conn.fetchall("""
            SELECT DISTINCT LEO_ROLE_NAME FROM dbo.LEO_TITLE_PAYCOM_MAP ORDER BY LEO_ROLE_NAME
        """)
        return jsonify([r[0] for r in rows])
    finally:
        conn.close()


@edm_bp.route("/api/leo-mapping", methods=["POST"])
@login_required
def add_leo_mapping():
    """Add a new Paycom Title → LEO Role mapping."""
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    title_paycom = (data.get("title_paycom") or "").strip().upper()
    leo_role_name = (data.get("leo_role_name") or "").strip().upper()
    match_type = (data.get("match_type") or "EXACT").strip().upper()
    notes = (data.get("notes") or "").strip() or None
    if not title_paycom or not leo_role_name:
        return jsonify({"error": "title_paycom and leo_role_name required"}), 400
    if match_type not in ("EXACT", "LIKE"):
        return jsonify({"error": "match_type must be EXACT or LIKE"}), 400
    try:
        priority = int(data.get("priority")) if data.get("priority") not in (None, "") else 100
    except (TypeError, ValueError):
        return jsonify({"error": "priority must be a number"}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        existing = conn.fetchall(
            "SELECT 1 FROM dbo.LEO_TITLE_PAYCOM_MAP WHERE TITLE_PAYCOM = ? AND MATCH_TYPE = ?",
            (title_paycom, match_type))
        if existing:
            return jsonify({"error": f"A {match_type} mapping for that title already exists"}), 409
        conn.execute("""
            INSERT INTO dbo.LEO_TITLE_PAYCOM_MAP
                (TITLE_PAYCOM, LEO_ROLE_NAME, MATCH_TYPE, PRIORITY, ENABLED, NOTES)
            VALUES (?, ?, ?, ?, 1, ?)
        """, (title_paycom, leo_role_name, match_type, priority, notes))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@edm_bp.route("/api/leo-mapping", methods=["PATCH"])
@login_required
def update_leo_mapping():
    """Update a single field on a LEO mapping row, keyed by map_id."""
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    map_id = data.get("map_id")
    field = data.get("field")
    value = data.get("value")
    allowed = {
        "title_paycom": "TITLE_PAYCOM", "leo_role_name": "LEO_ROLE_NAME",
        "match_type": "MATCH_TYPE", "priority": "PRIORITY",
        "enabled": "ENABLED", "notes": "NOTES"
    }
    if not map_id or field not in allowed:
        return jsonify({"error": "invalid request"}), 400
    col = allowed[field]
    if field in ("title_paycom", "leo_role_name", "match_type"):
        value = (value or "").strip().upper()
        if not value:
            return jsonify({"error": f"{field} cannot be blank"}), 400
        if field == "match_type" and value not in ("EXACT", "LIKE"):
            return jsonify({"error": "match_type must be EXACT or LIKE"}), 400
    elif field == "priority":
        try:
            value = int(value)
        except (TypeError, ValueError):
            return jsonify({"error": "priority must be a number"}), 400
    elif field == "enabled":
        value = 1 if value in (True, "true", "1", 1) else 0
    elif field == "notes":
        value = (value or "").strip() or None
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        if field in ("title_paycom", "match_type"):
            current = conn.fetchall(
                "SELECT TITLE_PAYCOM, MATCH_TYPE FROM dbo.LEO_TITLE_PAYCOM_MAP WHERE MAP_ID = ?", (map_id,))
            if not current:
                return jsonify({"error": "mapping not found"}), 404
            new_title = value if field == "title_paycom" else current[0][0]
            new_match = value if field == "match_type" else current[0][1]
            dupe = conn.fetchall(
                "SELECT 1 FROM dbo.LEO_TITLE_PAYCOM_MAP WHERE TITLE_PAYCOM = ? AND MATCH_TYPE = ? AND MAP_ID <> ?",
                (new_title, new_match, map_id))
            if dupe:
                return jsonify({"error": f"A {new_match} mapping for that title already exists"}), 409
        conn.execute(f"UPDATE dbo.LEO_TITLE_PAYCOM_MAP SET [{col}] = ? WHERE MAP_ID = ?",
                     (value, map_id))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@edm_bp.route("/api/leo-mapping", methods=["DELETE"])
@login_required
def delete_leo_mapping():
    """Delete a LEO mapping row."""
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    map_id = data.get("map_id")
    if not map_id:
        return jsonify({"error": "map_id required"}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute("DELETE FROM dbo.LEO_TITLE_PAYCOM_MAP WHERE MAP_ID = ?", (map_id,))
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
    dept = (data.get("entrata_department") or "").strip().upper()
    perm = (data.get("entrata_permission_group") or "").strip().upper()
    if not tg:
        return jsonify({"error": "title_group required"}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        existing = conn.fetchall(
            "SELECT 1 FROM dbo.EMP_ENTRATA_TITLE_GROUP_MAPPING WHERE TITLE_GROUP = ?", (tg,))
        if existing:
            return jsonify({"error": "Title Group already mapped"}), 409
        _ensure_entrata_option(conn, "department", dept)
        _ensure_entrata_option(conn, "permission_group", perm)
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
    value = (data.get("value") or "").strip().upper()
    valid_fields = {"entrata_department": "ENTRATA_DEPARTMENT",
                    "entrata_permission_group": "ENTRATA_PERMISSION_GROUP"}
    if not tg or field not in valid_fields:
        return jsonify({"error": "invalid request"}), 400
    col = valid_fields[field]
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        if field == "entrata_department":
            _ensure_entrata_option(conn, "department", value)
        elif field == "entrata_permission_group":
            _ensure_entrata_option(conn, "permission_group", value)
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
    if not data or "title_group" not in data:
        return jsonify({"error": "title_group required"}), 400
    tg = (data.get("title_group") or "").strip().upper()
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute("DELETE FROM dbo.EMP_ENTRATA_TITLE_GROUP_MAPPING WHERE TITLE_GROUP = ?", (tg,))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


# ─── ENTRATA PERMISSION ASSIGNMENTS TAB ───────────────────────────────────────

def _date_to_int(value):
    if value in (None, ""):
        return None
    s = str(value).strip()
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return int(s.replace("-", ""))
    if len(s) == 8 and s.isdigit():
        return int(s)
    raise ValueError("date must be YYYY-MM-DD or YYYYMMDD")


def _ensure_entrata_option(conn, kind, value):
    value = (value or "").strip().upper()
    if not value:
        return
    config = _entrata_option_config()
    if kind not in config or not config[kind].get("table"):
        raise ValueError("invalid option kind")
    table, column = config[kind]["table"], config[kind]["column"]
    existing = conn.fetchall(
        f"SELECT 1 FROM dbo.[{table}] WHERE UPPER([{column}]) = ?",
        (value,)
    )
    if not existing:
        conn.execute(f"INSERT INTO dbo.[{table}] ([{column}], FLAG_ACTIVE) VALUES (?, 1)", (value,))


def _entrata_option_config():
    return {
        "permission_group": {
            "table": "EMP_ENTRATA_PERMISSION_GROUP",
            "column": "Entrata_Permission_Group",
            "usage": [
                ("EMP_ENTRATA_TITLE_GROUP_MAPPING", "ENTRATA_PERMISSION_GROUP"),
                ("EMP_ENTRATA_GROUP_ASSIGNMENTS", "ENTRATA_PERMISSION_GROUP"),
            ],
        },
        "department": {
            "table": "EMP_ENTRATA_DEPARTMENT",
            "column": "ENTRATA_DEPARTMENT",
            "usage": [
                ("EMP_ENTRATA_TITLE_GROUP_MAPPING", "ENTRATA_DEPARTMENT"),
                ("EMP_ENTRATA_GROUP_ASSIGNMENTS", "ENTRATA_DEPARTMENT"),
            ],
        },
        "property_group": {
            "table": "EMP_ENTRATA_PROPERTY_GROUP",
            "column": "ENTRATA_PROPERTY_GROUP",
            "usage": [("EMP_ENTRATA_GROUP_ASSIGNMENTS", "ENTRATA_PROPERTY_GROUP")],
        },
        "type": {
            "table": None,
            "column": "TYPE",
            "usage": [("EMP_ENTRATA_GROUP_ASSIGNMENTS", "TYPE")],
        },
    }


def _entrata_option_usage(conn, kind, value):
    value = (value or "").strip().upper()
    config = _entrata_option_config()[kind]
    total = 0
    details = []
    for table, column in config["usage"]:
        count = conn.fetchall(
            f"SELECT COUNT(*) FROM dbo.[{table}] WHERE UPPER([{column}]) = ?",
            (value,)
        )[0][0]
        total += count
        if count:
            details.append({"table": f"dbo.{table}", "column": column, "count": count})
    return total, details


def _lookup_employee(emp_code):
    env = _get_env()
    conn = SafeConnection(env, "WH_STAGING", None)
    try:
        rows = conn.fetchall("""
            SELECT TOP 1 EMPLOYEE_KEY, EMPLOYEE_CODE, NAME_FIRST, NAME_LAST
            FROM dbo.EMPLOYEE_F
            WHERE EMPLOYEE_CODE = ? AND LOAD_TYPE <> 'PRE-HIRE'
            ORDER BY CASE WHEN STATUS NOT IN ('TERMINATED', 'DECEASED') THEN 0 ELSE 1 END
        """, (emp_code,))
        if not rows:
            return None
        r = rows[0]
        return {"employee_key": r[0], "employee_code": r[1], "name_first": r[2], "name_last": r[3]}
    finally:
        conn.close()


@edm_bp.route("/api/entrata-group-assignments", methods=["GET"])
@login_required
def get_entrata_group_assignments():
    """Get rows from EMP_ENTRATA_GROUP_ASSIGNMENTS."""
    check = _require_access()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        rows = conn.fetchall("""
            SELECT ID, EMPLOYEE_KEY, EMPLOYEE_CODE, NAME_FIRST, NAME_LAST,
                   ENTRATA_PERMISSION_GROUP, ENTRATA_DEPARTMENT, ENTRATA_PROPERTY_GROUP,
                   DATE_START, DATE_END, FLAG_ACTIVE, TYPE
            FROM dbo.EMP_ENTRATA_GROUP_ASSIGNMENTS
            ORDER BY NAME_LAST, NAME_FIRST, DATE_START DESC
        """)
        return jsonify([{
            "id": r[0], "employee_key": r[1], "employee_code": r[2],
            "name_first": r[3], "name_last": r[4],
            "entrata_permission_group": r[5], "entrata_department": r[6],
            "entrata_property_group": r[7], "date_start": r[8], "date_end": r[9],
            "flag_active": r[10], "type": r[11]
        } for r in rows])
    finally:
        conn.close()


@edm_bp.route("/api/entrata-group-assignments", methods=["POST"])
@login_required
def add_entrata_group_assignment():
    """Add one employee Entrata permission assignment."""
    check = _require_access()
    if check:
        return check
    data = request.get_json() or {}
    emp_code = (data.get("employee_code") or "").strip().upper()
    perm = (data.get("entrata_permission_group") or "").strip().upper()
    dept = (data.get("entrata_department") or "").strip().upper()
    prop_group = (data.get("entrata_property_group") or "").strip().upper()
    assignment_type = (data.get("type") or "").strip().upper()
    if not emp_code or not perm or not dept or not prop_group:
        return jsonify({"error": "employee, permission group, department, and property group are required"}), 400
    try:
        date_start = _date_to_int(data.get("date_start"))
        date_end = _date_to_int(data.get("date_end"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not date_start:
        return jsonify({"error": "date_start is required"}), 400
    employee = _lookup_employee(emp_code)
    if not employee:
        return jsonify({"error": f"Employee code {emp_code} not found"}), 404

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        _ensure_entrata_option(conn, "permission_group", perm)
        _ensure_entrata_option(conn, "department", dept)
        _ensure_entrata_option(conn, "property_group", prop_group)
        conn.execute("""
            INSERT INTO dbo.EMP_ENTRATA_GROUP_ASSIGNMENTS
                (EMPLOYEE_KEY, DATE_END, DATE_START, EMPLOYEE_CODE, FLAG_ACTIVE,
                 NAME_FIRST, NAME_LAST, ENTRATA_PERMISSION_GROUP, ENTRATA_DEPARTMENT,
                 ENTRATA_PROPERTY_GROUP, TYPE)
            VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
        """, (
            employee["employee_key"], date_end, date_start, employee["employee_code"],
            employee["name_first"], employee["name_last"], perm, dept, prop_group,
            assignment_type or None
        ))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@edm_bp.route("/api/entrata-group-assignments/<int:assignment_id>", methods=["PATCH"])
@login_required
def update_entrata_group_assignment(assignment_id):
    """Autosave one field on an Entrata permission assignment."""
    check = _require_access()
    if check:
        return check
    data = request.get_json() or {}
    field = data.get("field")
    value = data.get("value")
    valid_fields = {
        "entrata_permission_group": "ENTRATA_PERMISSION_GROUP",
        "entrata_department": "ENTRATA_DEPARTMENT",
        "entrata_property_group": "ENTRATA_PROPERTY_GROUP",
        "date_start": "DATE_START",
        "date_end": "DATE_END",
        "flag_active": "FLAG_ACTIVE",
        "type": "TYPE",
    }
    if field not in valid_fields:
        return jsonify({"error": "invalid field"}), 400
    try:
        if field in ("date_start", "date_end"):
            value = _date_to_int(value)
        elif field == "flag_active":
            value = 1 if value in (True, 1, "1", "true", "ACTIVE", "Active") else 0
        else:
            value = (value or "").strip().upper() or None
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        if field in ("entrata_permission_group", "entrata_department", "entrata_property_group"):
            option_kind = {
                "entrata_permission_group": "permission_group",
                "entrata_department": "department",
                "entrata_property_group": "property_group",
            }[field]
            _ensure_entrata_option(conn, option_kind, value)
        conn.execute(
            f"UPDATE dbo.EMP_ENTRATA_GROUP_ASSIGNMENTS SET [{valid_fields[field]}] = ? WHERE ID = ?",
            (value, assignment_id)
        )
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@edm_bp.route("/api/entrata-group-assignments/<int:assignment_id>", methods=["DELETE"])
@login_required
def delete_entrata_group_assignment(assignment_id):
    """Delete one Entrata permission assignment."""
    check = _require_access()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute("DELETE FROM dbo.EMP_ENTRATA_GROUP_ASSIGNMENTS WHERE ID = ?", (assignment_id,))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@edm_bp.route("/api/entrata-assignment-options", methods=["GET"])
@login_required
def get_entrata_assignment_options():
    """Get active lookup values for Entrata assignment dropdowns."""
    check = _require_access()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        permission_groups = conn.fetchall("""
            SELECT DISTINCT V FROM (
                SELECT UPPER(LTRIM(RTRIM(Entrata_Permission_Group))) AS V
                FROM dbo.EMP_ENTRATA_PERMISSION_GROUP
                WHERE Flag_Active = 1 AND Entrata_Permission_Group IS NOT NULL
                UNION
                SELECT UPPER(LTRIM(RTRIM(ENTRATA_PERMISSION_GROUP))) AS V
                FROM dbo.EMP_ENTRATA_GROUP_ASSIGNMENTS
                WHERE ENTRATA_PERMISSION_GROUP IS NOT NULL
            ) x WHERE V <> '' ORDER BY V
        """)
        departments = conn.fetchall("""
            SELECT DISTINCT V FROM (
                SELECT UPPER(LTRIM(RTRIM(ENTRATA_DEPARTMENT))) AS V
                FROM dbo.EMP_ENTRATA_DEPARTMENT
                WHERE FLAG_ACTIVE = 1 AND ENTRATA_DEPARTMENT IS NOT NULL
                UNION
                SELECT UPPER(LTRIM(RTRIM(ENTRATA_DEPARTMENT))) AS V
                FROM dbo.EMP_ENTRATA_GROUP_ASSIGNMENTS
                WHERE ENTRATA_DEPARTMENT IS NOT NULL
            ) x WHERE V <> '' ORDER BY V
        """)
        property_groups = conn.fetchall("""
            SELECT DISTINCT V FROM (
                SELECT UPPER(LTRIM(RTRIM(ENTRATA_PROPERTY_GROUP))) AS V
                FROM dbo.EMP_ENTRATA_PROPERTY_GROUP
                WHERE FLAG_ACTIVE = 1 AND ENTRATA_PROPERTY_GROUP IS NOT NULL
                UNION
                SELECT UPPER(LTRIM(RTRIM(ENTRATA_PROPERTY_GROUP))) AS V
                FROM dbo.EMP_ENTRATA_GROUP_ASSIGNMENTS
                WHERE ENTRATA_PROPERTY_GROUP IS NOT NULL
            ) x WHERE V <> '' ORDER BY V
        """)
        types = conn.fetchall("""
            SELECT DISTINCT UPPER(LTRIM(RTRIM(TYPE)))
            FROM dbo.EMP_ENTRATA_GROUP_ASSIGNMENTS
            WHERE TYPE IS NOT NULL AND LTRIM(RTRIM(TYPE)) <> ''
            ORDER BY UPPER(LTRIM(RTRIM(TYPE)))
        """)
        return jsonify({
            "permission_groups": [r[0] for r in permission_groups],
            "departments": [r[0] for r in departments],
            "property_groups": [r[0] for r in property_groups],
            "types": [r[0] for r in types],
        })
    finally:
        conn.close()


@edm_bp.route("/api/entrata-assignment-options/<kind>", methods=["POST"])
@login_required
def add_entrata_assignment_option(kind):
    """Create a lookup value for permission, department, or property group."""
    check = _require_access()
    if check:
        return check
    value = ((request.get_json() or {}).get("value") or "").strip().upper()
    if not value:
        return jsonify({"error": "value required"}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        _ensure_entrata_option(conn, kind, value)
        conn.commit()
        return jsonify({"ok": True})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        conn.close()


@edm_bp.route("/api/entrata-assignment-options/<kind>", methods=["DELETE"])
@login_required
def delete_entrata_assignment_option(kind):
    """Delete a lookup value, requiring replacement when it is in use."""
    check = _require_access()
    if check:
        return check
    config = _entrata_option_config()
    if kind not in config:
        return jsonify({"error": "invalid option kind"}), 400
    data = request.get_json() or {}
    value = (data.get("value") or "").strip().upper()
    replacement = (data.get("replacement") or "").strip().upper()
    if not value:
        return jsonify({"error": "value required"}), 400
    if replacement == value:
        return jsonify({"error": "replacement must be different"}), 400

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        usage_count, usage_details = _entrata_option_usage(conn, kind, value)
        if usage_count and not replacement:
            return jsonify({
                "error": "value is in use; choose a replacement before deleting",
                "needs_replacement": True,
                "usage_count": usage_count,
                "usage": usage_details,
            }), 409
        if usage_count and replacement:
            if kind != "type":
                _ensure_entrata_option(conn, kind, replacement)
            for table, column in config[kind]["usage"]:
                conn.execute(
                    f"UPDATE dbo.[{table}] SET [{column}] = ? WHERE UPPER([{column}]) = ?",
                    (replacement, value)
                )
        if kind != "type":
            table = config[kind]["table"]
            column = config[kind]["column"]
            conn.execute(f"DELETE FROM dbo.[{table}] WHERE UPPER([{column}]) = ?", (value,))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@edm_bp.route("/api/entrata-assignment-employees", methods=["GET"])
@login_required
def search_entrata_assignment_employees():
    """Search employees for the Entrata assignment add form."""
    check = _require_access()
    if check:
        return check
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    env = _get_env()
    conn = SafeConnection(env, "WH_STAGING", None)
    try:
        rows = conn.fetchall("""
            SELECT TOP 20 EMPLOYEE_CODE, NAME_FIRST, NAME_LAST, TITLE, PROPERTY_NAME
            FROM dbo.EMPLOYEE_F
            WHERE LOAD_TYPE <> 'PRE-HIRE'
              AND STATUS NOT IN ('TERMINATED', 'DECEASED')
              AND (UPPER(NAME_FIRST) LIKE UPPER(?) + '%'
                   OR UPPER(NAME_LAST) LIKE UPPER(?) + '%'
                   OR UPPER(NAME_FIRST + ' ' + NAME_LAST) LIKE '%' + UPPER(?) + '%'
                   OR UPPER(EMPLOYEE_CODE) = UPPER(?))
            ORDER BY NAME_FIRST, NAME_LAST
        """, (q, q, q, q))
        return jsonify([{
            "employee_code": r[0], "name_first": r[1], "name_last": r[2],
            "title": r[3] or "", "property": r[4] or ""
        } for r in rows])
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
                   o.FLAG_SOFT_TERMINATION, o.EXPIRES_ON, o.ADDED_BY, o.ADDED_ON,
                   o.UPDATED_BY, o.UPDATED_ON, o.IS_ACTIVE
            FROM dbo.EMPLOYEE_SOFT_TERMINATION_OVERRIDES o
            ORDER BY o.NAME_LAST, o.NAME_FIRST
        """)
        return jsonify([{
            "employee_code": r[0], "name_first": r[1], "name_last": r[2],
            "reason": r[3],
            "flag_soft_termination": bool(r[4]) if r[4] is not None else True,
            "expires_on": r[5].isoformat() if r[5] else None,
            "added_by": r[6],
            "added_on": r[7].isoformat() if r[7] else None,
            "updated_by": r[8],
            "updated_on": r[9].isoformat() if r[9] else None,
            "is_active": bool(r[10]) if r[10] is not None else True
        } for r in rows])
    finally:
        conn.close()


@edm_bp.route("/api/soft-terminations/employees", methods=["GET"])
@login_required
def search_soft_termination_employees():
    """Search employees by code or name for soft termination overrides."""
    check = _require_access()
    if check:
        return check
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    env = _get_env()
    conn = SafeConnection(env, "WH_STAGING", None)
    try:
        rows = conn.fetchall("""
            SELECT TOP 20 EMPLOYEE_CODE, NAME_FIRST, NAME_LAST, TITLE, PROPERTY_NAME, STATUS
            FROM dbo.EMPLOYEE_F
            WHERE LOAD_TYPE <> 'PRE-HIRE'
              AND (UPPER(EMPLOYEE_CODE) = UPPER(?)
                   OR UPPER(NAME_FIRST) LIKE UPPER(?) + '%'
                   OR UPPER(NAME_LAST) LIKE UPPER(?) + '%'
                   OR UPPER(NAME_FIRST + ' ' + NAME_LAST) LIKE '%' + UPPER(?) + '%')
            ORDER BY CASE WHEN STATUS IN ('TERMINATED', 'DECEASED') THEN 1 ELSE 0 END,
                     NAME_FIRST, NAME_LAST
        """, (q, q, q, q))
        return jsonify([{
            "employee_code": r[0], "name_first": r[1], "name_last": r[2],
            "title": r[3] or "", "property": r[4] or "", "status": r[5] or ""
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
                (EMPLOYEE_CODE, FLAG_SOFT_TERMINATION, NAME_FIRST, NAME_LAST, REASON,
                 ADDED_BY, EXPIRES_ON, IS_ACTIVE)
            VALUES (?, 1, ?, ?, ?, ?, ?, 1)
        """, (emp_code, name_first, name_last, reason, user_email, expires_on))
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
        if "expires_on" in data:
            sets.append("EXPIRES_ON = ?")
            params.append(data["expires_on"] or None)
        if "is_active" in data:
            sets.append("FLAG_SOFT_TERMINATION = ?")
            params.append(1 if data["is_active"] else 0)
            sets.append("IS_ACTIVE = ?")
            params.append(1 if data["is_active"] else 0)
        if not sets:
            return jsonify({"error": "No fields to update"}), 400
        sets.append("UPDATED_BY = ?")
        params.append(user_email)
        sets.append("UPDATED_ON = SYSUTCDATETIME()")
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
