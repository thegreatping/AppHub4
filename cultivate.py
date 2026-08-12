"""Cultivate Nomination module — nominate associates for the Cultivate mentorship program."""
from flask import Blueprint, render_template, session, jsonify, request
from auth import login_required
from modules import MODULES, APP_ID_MAP
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection
from datetime import datetime

cultivate_bp = Blueprint("cultivate", __name__, url_prefix="/cultivate")

_env = None


def _get_env():
    global _env
    if _env is None:
        _env = load_env()
    return _env


def _require_access():
    """Check that the current user has access to Cultivate (app_id=22)."""
    if session.get("is_developer"):
        return None
    user_modules = session.get("user_modules", [])
    for m in user_modules:
        if m["id"] == 22:
            return None
    return jsonify({"error": "unauthorized"}), 403


def _is_admin():
    """Check if current user is an admin for Cultivate (APP_ID=22)."""
    if session.get("is_developer"):
        return True
    user = session.get("user", {})
    email = user.get("email", "").lower()
    if not email:
        return False
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    cur = conn.execute(
        "SELECT COUNT(*) FROM dbo.APP_ADMINS WHERE APP_ID = 22 AND LOWER(ADMIN_EMAIL) = ?",
        [email]
    )
    return cur.fetchone()[0] > 0


def _get_shell_context():
    """Build standard shell template context."""
    from config import APP_VERSION
    user_modules = session.get("user_modules", [])
    allowed_string_ids = set()
    for m in user_modules:
        string_id = APP_ID_MAP.get(m["id"])
        if string_id:
            allowed_string_ids.add(string_id)
    visible = [m for m in MODULES if m["id"] in allowed_string_ids] if user_modules else MODULES
    return dict(
        modules=visible,
        active_module="cultivate_nomination",
        user=session.get("user", {}),
        is_developer=session.get("is_developer", False),
        is_dev_mode=session.get("is_dev_mode", False),
        is_impersonating=session.get("is_impersonating", False),
        impersonating_user=session.get("impersonating_user", None),
        version=APP_VERSION,
    )


# ─── PAGE ROUTE ─────────────────────────────────────────────────────────────────

@cultivate_bp.route("/")
@login_required
def index():
    """Render the Cultivate Nomination page."""
    check = _require_access()
    if check:
        return check
    ctx = _get_shell_context()
    ctx["is_admin"] = _is_admin()
    return render_template("cultivate.html", **ctx)


# ─── API: EMPLOYEES (for dropdown) ─────────────────────────────────────────────

@cultivate_bp.route("/api/employees", methods=["GET"])
@login_required
def api_employees():
    """Return active employees eligible for nomination."""
    check = _require_access()
    if check:
        return check
    q = request.args.get("q", "").strip().lower()
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    sql = """
        SELECT NAME_FULL, TITLE, PROPERTY_NAME, DATETIME_HIRED, EMAIL
        FROM xtemp.EMPLOYEE_F
        WHERE STATUS = 'ACTIVE'
          AND (LOCATION IN ('PEAK HOME OFFICE', 'REMOTE ASSOCIATES')
               OR TITLE LIKE '%%MANAGER%%'
               OR TITLE = 'EXECUTIVE DIRECTOR')
        ORDER BY NAME_FULL
    """
    cur = conn.execute(sql)
    rows = cur.fetchall()
    results = []
    for r in rows:
        name = r[0] or ""
        if q and q not in name.lower():
            continue
        tenure = None
        if r[3]:
            try:
                days = (datetime.now() - r[3]).days
                tenure = round(days / 365.25, 1)
            except Exception:
                pass
        results.append({
            "name": name,
            "title": r[1] or "",
            "property": r[2] or "",
            "tenure": tenure,
            "email": r[4] or "",
        })
    return jsonify(results)


# ─── API: NOMINATIONS ───────────────────────────────────────────────────────────

@cultivate_bp.route("/api/nominations", methods=["GET"])
@login_required
def api_nominations():
    """Return all nominations (admin only)."""
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin access required"}), 403
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    cur = conn.execute("""
        SELECT ID, ASSOCIATE_NOMINATED, ASSOCIATE_POSITION, ASSOCIATE_LOCATION,
               ASSOCIATE_TENURE, ASSOCIATE_SOFT_SKILLS, ASSOCIATE_STANDING_CHOICE,
               DATE_CREATED, NOMINATED_BY, NOMINATION_REASON
        FROM dbo.CULTIVATE_NOMINATION
        ORDER BY ID DESC
    """)
    rows = cur.fetchall()
    results = []
    for r in rows:
        results.append({
            "id": r[0],
            "associate": r[1],
            "position": r[2],
            "location": r[3],
            "tenure": float(r[4]) if r[4] else None,
            "soft_skills": r[5],
            "standing": r[6],
            "date_created": r[7].strftime("%Y-%m-%d") if r[7] else None,
            "nominated_by": r[8],
            "reason": r[9],
        })
    return jsonify(results)


@cultivate_bp.route("/api/nominations", methods=["POST"])
@login_required
def api_submit_nomination():
    """Submit a new nomination."""
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    required = ["associate_nominated", "nomination_reason"]
    for field in required:
        if not data.get(field, "").strip():
            return jsonify({"error": f"Missing required field: {field}"}), 400

    user = session.get("user", {})
    from config import APP_VERSION

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    conn.execute("""
        INSERT INTO dbo.CULTIVATE_NOMINATION
            (ASSOCIATE_NOMINATED, ASSOCIATE_POSITION, ASSOCIATE_LOCATION,
             ASSOCIATE_TENURE, ASSOCIATE_SOFT_SKILLS, ASSOCIATE_STANDING_CHOICE,
             ASSOCIATE_STANDING_TEXT, DATE_CREATED, NOMINATED_BY,
             NOMINATION_REASON, PROD_VERSION)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        data.get("associate_nominated", "").strip(),
        data.get("associate_position", "").strip(),
        data.get("associate_location", "").strip(),
        data.get("associate_tenure"),
        data.get("associate_soft_skills", "").strip(),
        data.get("associate_standing_choice", "").strip() or None,
        data.get("associate_standing_text", "").strip() or None,
        datetime.now(),
        user.get("name", "Unknown"),
        data.get("nomination_reason", "").strip(),
        APP_VERSION,
    ])
    return jsonify({"success": True, "message": "Nomination submitted successfully."})


# ─── API: ADMINS ────────────────────────────────────────────────────────────────

@cultivate_bp.route("/api/admins", methods=["GET"])
@login_required
def api_admins():
    """Return admin list for Cultivate (admin only)."""
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
        WHERE APP_ID = 22
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


@cultivate_bp.route("/api/admins", methods=["POST"])
@login_required
def api_add_admin():
    """Add an admin for Cultivate (admin only)."""
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
    # Check if already exists
    cur = conn.execute(
        "SELECT COUNT(*) FROM dbo.APP_ADMINS WHERE APP_ID = 22 AND LOWER(ADMIN_EMAIL) = ?",
        [email]
    )
    if cur.fetchone()[0] > 0:
        return jsonify({"error": "Admin already exists"}), 409
    conn.execute("""
        INSERT INTO dbo.APP_ADMINS (APP_ID, APP_NAME, ADMIN_EMAIL, DATE_CREATED)
        VALUES (22, 'Cultivate Nomination', ?, ?)
    """, [email, datetime.now()])
    return jsonify({"success": True, "message": "Admin added."})


@cultivate_bp.route("/api/admins/<int:admin_id>", methods=["DELETE"])
@login_required
def api_remove_admin(admin_id):
    """Remove an admin for Cultivate (admin only)."""
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin access required"}), 403
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    conn.execute("DELETE FROM dbo.APP_ADMINS WHERE ID = ? AND APP_ID = 22", [admin_id])
    return jsonify({"success": True, "message": "Admin removed."})
