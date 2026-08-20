"""FastTrack Recommendation module — submit and track FastTrack promotion recommendations."""
from flask import Blueprint, render_template, session, jsonify, request
from auth import login_required
from modules import MODULES, APP_ID_MAP
from nav import build_nav_modules
import sys
from helpers import load_env, SafeConnection
from datetime import datetime

fasttrack_bp = Blueprint("fasttrack", __name__, url_prefix="/fasttrack")

_env = None


def _get_env():
    global _env
    if _env is None:
        _env = load_env()
    return _env


def _require_access():
    """Check that the current user has access to FastTrack (app_id=20)."""
    if session.get("is_developer"):
        return None
    user_modules = session.get("user_modules", [])
    for m in user_modules:
        if m["id"] == 20:
            return None
    return jsonify({"error": "unauthorized"}), 403


def _is_admin():
    """Check if current user is an admin for FastTrack (APP_ID=20)."""
    if session.get("is_developer"):
        return True
    user = session.get("user", {})
    email = user.get("email", "").lower()
    if not email:
        return False
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    cur = conn.execute(
        "SELECT COUNT(*) FROM dbo.APP_ADMINS WHERE APP_ID = 20 AND LOWER(ADMIN_EMAIL) = ?",
        [email]
    )
    return cur.fetchone()[0] > 0


def _get_shell_context():
    """Build standard shell template context."""
    from config import APP_VERSION
    visible = build_nav_modules()
    return dict(
        modules=visible,
        active_module="fasttrack_recommendation",
        user=session.get("user", {}),
        is_developer=session.get("is_developer", False),
        is_dev_mode=session.get("is_dev_mode", False),
        is_impersonating=session.get("is_impersonating", False),
        impersonating_user=session.get("impersonating_user", None),
        version=APP_VERSION,
    )


# ─── PAGE ROUTE ─────────────────────────────────────────────────────────────────

@fasttrack_bp.route("/")
@login_required
def index():
    """Render the FastTrack Recommendation page."""
    check = _require_access()
    if check:
        return check
    ctx = _get_shell_context()
    ctx["is_admin"] = _is_admin()
    return render_template("fasttrack.html", **ctx)


# ─── API: EMPLOYEES (for dropdown) ─────────────────────────────────────────────

@fasttrack_bp.route("/api/employees", methods=["GET"])
@login_required
def api_employees():
    """Return active employees for recommendation dropdown."""
    check = _require_access()
    if check:
        return check
    q = request.args.get("q", "").strip().lower()
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    sql = """
        SELECT NAME_FULL, TITLE, PROPERTY_NAME, DATETIME_HIRED
        FROM xtemp.EMPLOYEE_F
        WHERE STATUS = 'ACTIVE'
        ORDER BY NAME_FULL
    """
    cur = conn.execute(sql)
    rows = cur.fetchall()
    results = []
    for r in rows:
        name = r[0] or ""
        if q and q not in name.lower():
            continue
        date_hired = None
        if r[3]:
            try:
                date_hired = r[3].strftime("%m/%d/%Y")
            except Exception:
                pass
        results.append({
            "name": name,
            "title": r[1] or "",
            "property": r[2] or "",
            "date_hired": date_hired,
        })
    return jsonify(results)


# ─── API: RECOMMENDATIONS ───────────────────────────────────────────────────────

@fasttrack_bp.route("/api/recommendations", methods=["GET"])
@login_required
def api_recommendations():
    """Return all recommendations (admin only)."""
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin access required"}), 403
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    cur = conn.execute("""
        SELECT ID, EMPLOYEE_RECOMMENDED, CURRENT_POSITION, CURRENT_PROPERTY,
               RECOMMENDED_FASTTRACK, TIME_IN_CURRENT_POSITION, DATE_HIRED,
               ADDITIONAL_NOTES, MODIFIED_BY, DATE_MODIFIED
        FROM dbo.FASTTRACK_RECOMMENDATION
        ORDER BY ID DESC
    """)
    rows = cur.fetchall()
    results = []
    for r in rows:
        results.append({
            "id": r[0],
            "employee": r[1],
            "position": r[2],
            "property": r[3],
            "fasttrack": r[4],
            "time_in_position": r[5],
            "date_hired": r[6].strftime("%m/%d/%Y") if r[6] else None,
            "notes": r[7],
            "modified_by": r[8],
            "date_modified": r[9].strftime("%m/%d/%Y") if r[9] else None,
        })
    return jsonify(results)


@fasttrack_bp.route("/api/recommendations", methods=["POST"])
@login_required
def api_submit_recommendation():
    """Submit a new FastTrack recommendation."""
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    required = ["employee_recommended", "recommended_fasttrack", "time_in_current_position", "additional_notes"]
    for field in required:
        if not data.get(field, "").strip():
            return jsonify({"error": f"Missing required field: {field}"}), 400

    user = session.get("user", {})
    from config import APP_VERSION

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    conn.execute("""
        INSERT INTO dbo.FASTTRACK_RECOMMENDATION
            (EMPLOYEE_RECOMMENDED, CURRENT_PROPERTY, CURRENT_POSITION,
             RECOMMENDED_FASTTRACK, TIME_IN_CURRENT_POSITION, DATE_HIRED,
             ADDITIONAL_NOTES, MODIFIED_BY, DATE_MODIFIED, PROD_VERSION)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        data.get("employee_recommended", "").strip(),
        data.get("current_property", "").strip(),
        data.get("current_position", "").strip(),
        data.get("recommended_fasttrack", "").strip(),
        data.get("time_in_current_position", "").strip(),
        data.get("date_hired") or None,
        data.get("additional_notes", "").strip(),
        user.get("name", "Unknown"),
        datetime.now(),
        APP_VERSION,
    ])
    return jsonify({"success": True, "message": "Recommendation submitted successfully."})


# ─── API: ADMINS ────────────────────────────────────────────────────────────────

@fasttrack_bp.route("/api/admins", methods=["GET"])
@login_required
def api_admins():
    """Return admin list for FastTrack (admin only)."""
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin access required"}), 403
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    cur = conn.execute("""
        SELECT ID, ADMIN_EMAIL, DATE_CREATED
        FROM dbo.APP_ADMINS
        WHERE APP_ID = 20
        ORDER BY ID
    """)
    results = []
    for r in cur.fetchall():
        results.append({
            "id": r[0],
            "email": r[1],
            "date_created": r[2].strftime("%Y-%m-%d") if r[2] else None,
        })
    return jsonify(results)


@fasttrack_bp.route("/api/admins", methods=["POST"])
@login_required
def api_add_admin():
    """Add an admin for FastTrack (admin only)."""
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin access required"}), 403
    data = request.get_json()
    email = (data.get("email", "") if data else "").strip().lower()
    if not email:
        return jsonify({"error": "Email is required"}), 400

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    cur = conn.execute(
        "SELECT COUNT(*) FROM dbo.APP_ADMINS WHERE APP_ID = 20 AND LOWER(ADMIN_EMAIL) = ?",
        [email]
    )
    if cur.fetchone()[0] > 0:
        return jsonify({"error": "Admin already exists"}), 409
    conn.execute("""
        INSERT INTO dbo.APP_ADMINS (APP_ID, APP_NAME, ADMIN_EMAIL, DATE_CREATED)
        VALUES (20, 'FastTrack Recommendation', ?, ?)
    """, [email, datetime.now()])
    return jsonify({"success": True, "message": "Admin added."})


@fasttrack_bp.route("/api/admins/<int:admin_id>", methods=["DELETE"])
@login_required
def api_remove_admin(admin_id):
    """Remove an admin for FastTrack (admin only)."""
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin access required"}), 403
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    conn.execute("DELETE FROM dbo.APP_ADMINS WHERE ID = ? AND APP_ID = 20", [admin_id])
    return jsonify({"success": True, "message": "Admin removed."})
