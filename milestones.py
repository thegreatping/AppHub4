"""Milestones module — track monthly employee points by property."""
import sys
from datetime import date
from flask import Blueprint, render_template, session, jsonify, request
from auth import login_required
from modules import MODULES, APP_ID_MAP

sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

milestones_bp = Blueprint("milestones", __name__, url_prefix="/milestones")

_env = None


def _get_env():
    global _env
    if _env is None:
        _env = load_env()
    return _env


def _get_db():
    return SafeConnection(_get_env(), "DB_APP_SUPPORT", None, direct=True)


def _require_access():
    if session.get("is_developer"):
        return None
    for m in session.get("user_modules", []):
        if m["id"] == 1:
            return None
    return jsonify({"error": "unauthorized"}), 403


def _get_shell_context():
    from config import APP_VERSION
    user_modules = session.get("user_modules", [])
    allowed = {APP_ID_MAP.get(m["id"]) for m in user_modules}
    visible = [m for m in MODULES if m["id"] in allowed] if user_modules else MODULES
    return dict(
        modules=visible,
        active_module="milestones",
        user=session.get("user", {}),
        is_developer=session.get("is_developer", False),
        is_dev_mode=session.get("is_dev_mode", False),
        is_impersonating=session.get("is_impersonating", False),
        impersonating_user=session.get("impersonating_user", None),
        version=APP_VERSION,
    )


def _recent_months(n=6):
    """Return list of n YYYYMM ints descending from current month."""
    today = date.today()
    y, m = today.year, today.month
    months = []
    for _ in range(n):
        months.append(y * 100 + m)
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return months


# ── Routes ───────────────────────────────────────────────────────────────────

@milestones_bp.route("/")
@login_required
def index():
    check = _require_access()
    if check:
        return check
    return render_template("milestones.html", **_get_shell_context())


@milestones_bp.route("/api/properties")
@login_required
def api_properties():
    check = _require_access()
    if check:
        return check
    conn = _get_db()
    rows = conn.execute("""
        SELECT DISTINCT PROPERTY_KEY, PROPERTY_NAME, PROPERTY_TYPE
        FROM dbo.MILESTONES_EMPLOYEES
        ORDER BY PROPERTY_NAME
    """).fetchall()
    return jsonify([{"key": r[0], "name": r[1], "ptype": r[2] or ""} for r in rows])


@milestones_bp.route("/api/employees")
@login_required
def api_employees():
    check = _require_access()
    if check:
        return check
    pk = request.args.get("property_key", type=int)
    if not pk:
        return jsonify({"employees": [], "months": []})
    conn = _get_db()
    months = _recent_months(12)
    # Source rule: never show data older than Nov 2025 (YYYYMM >= 202511)
    months = [m for m in months if m >= 202511]

    emps = conn.execute("""
        SELECT EMPLOYEE_CODE, EMPLOYEE_NAME, MILESTONE_TYPE
        FROM dbo.MILESTONES_EMPLOYEES
        WHERE PROPERTY_KEY = ?
        ORDER BY MILESTONE_TYPE, EMPLOYEE_NAME
    """, [pk]).fetchall()

    if not emps:
        return jsonify({"employees": [], "months": months})

    codes = [e[0] for e in emps]
    ph_months = ",".join(["?"] * len(months))
    ph_codes  = ",".join(["?"] * len(codes))
    pts_rows = conn.execute(f"""
        SELECT EMPLOYEE_CODE, YYYYMM, POINTS
        FROM dbo.MILESTONES_POINTS
        WHERE PROPERTY_KEY = ? AND YYYYMM IN ({ph_months}) AND EMPLOYEE_CODE IN ({ph_codes})
    """, [pk] + months + codes).fetchall()

    pts = {}
    for r in pts_rows:
        pts.setdefault(r[0], {})[r[1]] = r[2]

    result = []
    for code, name, mtype in emps:
        result.append({
            "code":   code,
            "name":   name,
            "type":   mtype or "",
            "points": {str(m): pts.get(code, {}).get(m) for m in months},
        })
    # Lock edits from the 20th onward so the prior month can be reconciled cleanly
    edit_locked = date.today().day >= 20
    return jsonify({"employees": result, "months": months, "edit_locked": edit_locked})


@milestones_bp.route("/api/points/save", methods=["POST"])
@login_required
def api_points_save():
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    emp_code     = data.get("employee_code")
    yyyymm       = data.get("yyyymm")
    points_raw   = data.get("points")
    property_key = data.get("property_key")
    if not emp_code or not yyyymm:
        return jsonify({"error": "missing params"}), 400

    yyyymm = int(yyyymm)
    points = int(points_raw) if points_raw not in (None, "", "null") else None

    # Block saves from the 20th onward
    if date.today().day >= 20:
        return jsonify({"error": "locked", "message": "Edits are locked after the 20th of the month."}), 403

    user = session.get("user", {})
    by_name = user.get("name", "")
    by_code = user.get("email", "").split("@")[0].upper()

    conn = _get_db()
    emp_row = conn.execute("""
        SELECT LOCATION, PROPERTY_NAME FROM dbo.MILESTONES_EMPLOYEES
        WHERE PROPERTY_KEY = ? AND EMPLOYEE_CODE = ?
    """, [property_key, emp_code]).fetchone()
    location  = emp_row[0] if emp_row else ""
    prop_name = emp_row[1] if emp_row else ""

    existing = conn.execute(
        "SELECT 1 FROM dbo.MILESTONES_POINTS WHERE YYYYMM = ? AND EMPLOYEE_CODE = ?",
        [yyyymm, emp_code]
    ).fetchone()

    if points is None:
        if existing:
            conn.execute(
                "DELETE FROM dbo.MILESTONES_POINTS WHERE YYYYMM = ? AND EMPLOYEE_CODE = ?",
                [yyyymm, emp_code]
            )
    elif existing:
        conn.execute("""
            UPDATE dbo.MILESTONES_POINTS
            SET POINTS = ?, MODIFIED_BY_NAME = ?, MODIFIED_BY_CODE = ?, MODIFIED_DATETIME = GETDATE()
            WHERE YYYYMM = ? AND EMPLOYEE_CODE = ?
        """, [points, by_name, by_code, yyyymm, emp_code])
    else:
        conn.execute("""
            INSERT INTO dbo.MILESTONES_POINTS
                (YYYYMM, EMPLOYEE_CODE, POINTS, LOCATION, PROPERTY_KEY, PROPERTY_NAME,
                 MODIFIED_BY_NAME, MODIFIED_BY_CODE, MODIFIED_DATETIME)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
        """, [yyyymm, emp_code, points, location, property_key, prop_name, by_name, by_code])

    conn.commit()
    return jsonify({"ok": True})
