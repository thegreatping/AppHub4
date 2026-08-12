"""Mentor Certification module — track and manage mentor certification enrollment."""
from flask import Blueprint, render_template, session, jsonify, request
from auth import login_required
from modules import MODULES, APP_ID_MAP
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection
from datetime import datetime

mentor_cert_bp = Blueprint("mentor_cert", __name__, url_prefix="/mentor-cert")

_env = None


def _get_env():
    global _env
    if _env is None:
        _env = load_env()
    return _env


def _require_access():
    if session.get("is_developer"):
        return None
    user_modules = session.get("user_modules", [])
    for m in user_modules:
        if m["id"] == 21:
            return None
    return jsonify({"error": "unauthorized"}), 403


def _is_admin():
    if session.get("is_developer"):
        return True
    user = session.get("user", {})
    email = user.get("email", "").lower()
    if not email:
        return False
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    cur = conn.execute(
        "SELECT COUNT(*) FROM dbo.APP_ADMINS WHERE APP_ID = 21 AND LOWER(ADMIN_EMAIL) = ?",
        [email]
    )
    return cur.fetchone()[0] > 0


def _get_shell_context():
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
        active_module="mentor_certification",
        user=session.get("user", {}),
        is_developer=session.get("is_developer", False),
        is_dev_mode=session.get("is_dev_mode", False),
        is_impersonating=session.get("is_impersonating", False),
        impersonating_user=session.get("impersonating_user", None),
        version=APP_VERSION,
    )


@mentor_cert_bp.route("/")
@login_required
def index():
    check = _require_access()
    if check:
        return check
    ctx = _get_shell_context()
    ctx["is_admin"] = _is_admin()
    return render_template("mentor_cert.html", **ctx)


@mentor_cert_bp.route("/api/employees", methods=["GET"])
@login_required
def api_employees():
    check = _require_access()
    if check:
        return check
    q = request.args.get("q", "").strip().lower()
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    cur = conn.execute("""
        SELECT NAME_FULL, TITLE, PROPERTY_NAME, DATETIME_HIRED
        FROM xtemp.EMPLOYEE_F
        WHERE STATUS = 'ACTIVE'
        ORDER BY NAME_FULL
    """)
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


@mentor_cert_bp.route("/api/certifications", methods=["GET"])
@login_required
def api_certifications():
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin access required"}), 403
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    cur = conn.execute("""
        SELECT ID, MENTOR_NAME, CURRENT_POSITION, CURRENT_PROPERTY_NAME,
               ORIGINAL_SUBMISSION_DATE, SUMMARY_NOTES, SUBMITTED_BY, MODIFIED_DATETIME
        FROM dbo.MENTOR_CERTIFICATION
        ORDER BY ID DESC
    """)
    results = []
    for r in cur.fetchall():
        results.append({
            "id": r[0],
            "mentor_name": r[1],
            "position": r[2],
            "property": r[3],
            "date_hired": r[4].strftime("%m/%d/%Y") if r[4] else None,
            "notes": r[5],
            "submitted_by": r[6],
            "date_modified": r[7].strftime("%m/%d/%Y") if r[7] else None,
        })
    return jsonify(results)


@mentor_cert_bp.route("/api/certifications", methods=["POST"])
@login_required
def api_submit():
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    if not data.get("mentor_name", "").strip():
        return jsonify({"error": "Please select an associate."}), 400
    if not data.get("summary_notes", "").strip():
        return jsonify({"error": "Summary notes are required."}), 400

    user = session.get("user", {})
    from config import APP_VERSION
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    conn.execute("""
        INSERT INTO dbo.MENTOR_CERTIFICATION
            (MENTOR_NAME, CURRENT_POSITION, CURRENT_PROPERTY_NAME,
             ORIGINAL_SUBMISSION_DATE, SUMMARY_NOTES, SUBMITTED_BY,
             MODIFIED_DATETIME, PROD_VERSION)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        data.get("mentor_name", "").strip(),
        data.get("current_position", "").strip(),
        data.get("current_property", "").strip(),
        data.get("date_hired") or None,
        data.get("summary_notes", "").strip(),
        user.get("name", "Unknown"),
        datetime.now(),
        APP_VERSION,
    ])
    return jsonify({"success": True, "message": "Enrollment submitted successfully."})


@mentor_cert_bp.route("/api/admins", methods=["GET"])
@login_required
def api_admins():
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin access required"}), 403
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    cur = conn.execute("""
        SELECT ID, ADMIN_EMAIL, DATE_CREATED
        FROM dbo.APP_ADMINS WHERE APP_ID = 21 ORDER BY ID
    """)
    return jsonify([{"id": r[0], "email": r[1], "date_created": r[2].strftime("%Y-%m-%d") if r[2] else None} for r in cur.fetchall()])


@mentor_cert_bp.route("/api/admins", methods=["POST"])
@login_required
def api_add_admin():
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
    cur = conn.execute("SELECT COUNT(*) FROM dbo.APP_ADMINS WHERE APP_ID = 21 AND LOWER(ADMIN_EMAIL) = ?", [email])
    if cur.fetchone()[0] > 0:
        return jsonify({"error": "Admin already exists"}), 409
    conn.execute("INSERT INTO dbo.APP_ADMINS (APP_ID, APP_NAME, ADMIN_EMAIL, DATE_CREATED) VALUES (21, 'Mentor Certification', ?, ?)", [email, datetime.now()])
    return jsonify({"success": True, "message": "Admin added."})


@mentor_cert_bp.route("/api/admins/<int:admin_id>", methods=["DELETE"])
@login_required
def api_remove_admin(admin_id):
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin access required"}), 403
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    conn.execute("DELETE FROM dbo.APP_ADMINS WHERE ID = ? AND APP_ID = 21", [admin_id])
    return jsonify({"success": True, "message": "Admin removed."})
