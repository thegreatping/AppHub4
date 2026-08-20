"""Mindset Award Nomination module.

Data store: SharePoint list 'Peak Mindset Recognition'
              on peakcampus.sharepoint.com/sites/BaseCampApps
List GUID : d616e4e3-e7a5-4ee4-9d98-fc8c338c2783
Auth      : Microsoft Graph API (MSAL client-credentials flow, same as Peak Link)
"""
from flask import Blueprint, render_template, session, jsonify, request
from auth import login_required
from modules import MODULES, APP_ID_MAP
from nav import build_nav_modules
import sys
from helpers import load_env, SafeConnection
from datetime import datetime

mindset_bp = Blueprint("mindset", __name__, url_prefix="/mindset")

# ── SharePoint constants ──────────────────────────────────────────────────────────
SP_SITE_PATH = "peakcampus.sharepoint.com:/sites/BaseCampApps"
SP_LIST_ID   = "d616e4e3-e7a5-4ee4-9d98-fc8c338c2783"

# SharePoint internal column names (Graph API uses these, NOT display names)
_COL_NOMINEE   = "Employee_Name"             # display: Person_Nominated
_COL_POSITION  = "Position"
_COL_LOCATION  = "Location"                  # display: Current Property/Location
_COL_MINDSET   = "Peak_Mindset_Represented"  # choice field
_COL_STANDARD  = "PeakStandardRepresented"   # choice field
_COL_SUBMITTER = "Submitted_By_Employee_Name" # display: Submitted_By_Employee_Code
_COL_COMMENTS  = "Comments"                  # nomination reason

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
        if m["id"] == 24:
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
        "SELECT COUNT(*) FROM dbo.APP_ADMINS WHERE APP_ID = 24 AND LOWER(ADMIN_EMAIL) = ?",
        [email]
    )
    return cur.fetchone()[0] > 0


def _get_shell_context():
    from config import APP_VERSION
    visible = build_nav_modules()
    return dict(
        modules=visible,
        active_module="mindset_award_nomination",
        user=session.get("user", {}),
        is_developer=session.get("is_developer", False),
        is_dev_mode=session.get("is_dev_mode", False),
        is_impersonating=session.get("is_impersonating", False),
        impersonating_user=session.get("impersonating_user", None),
        version=APP_VERSION,
    )


@mindset_bp.route("/")
@login_required
def index():
    check = _require_access()
    if check:
        return check
    ctx = _get_shell_context()
    ctx["is_admin"] = _is_admin()
    return render_template("mindset.html", **ctx)


@mindset_bp.route("/api/employees", methods=["GET"])
@login_required
def api_employees():
    check = _require_access()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    cur = conn.execute("""
        SELECT NAME_FULL, TITLE, PROPERTY_NAME
        FROM xtemp.EMPLOYEE_F
        WHERE STATUS = 'ACTIVE'
        ORDER BY NAME_FULL
    """)
    rows = cur.fetchall()
    results = []
    for r in rows:
        results.append({
            "name": r[0] or "",
            "title": r[1] or "",
            "property": r[2] or "",
        })
    return jsonify(results)


def _sp():
    """Return (site_id, list_id) tuple, resolving site lazily."""
    from graph_client import get_site_id
    return get_site_id(SP_SITE_PATH), SP_LIST_ID


@mindset_bp.route("/api/nominations", methods=["GET"])
@login_required
def api_nominations():
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin access required"}), 403
    try:
        from graph_client import list_items
        site_id, list_id = _sp()
        rows = list_items(site_id, list_id)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    except Exception as exc:
        return jsonify({"error": f"SharePoint error: {exc}"}), 500

    results = []
    for row in rows:
        results.append({
            "id":           row.get("_item_id", ""),
            "nominee":      row.get(_COL_NOMINEE, ""),
            "position":     row.get(_COL_POSITION, ""),
            "property":     row.get(_COL_LOCATION, ""),
            "mindset_value": row.get(_COL_MINDSET, ""),
            "peak_standard": row.get(_COL_STANDARD, ""),
            "nominated_by": row.get(_COL_SUBMITTER, ""),
            "reason":       row.get(_COL_COMMENTS, ""),
            "date_created": row.get("Created", ""),
        })
    results.sort(key=lambda x: x["id"] if isinstance(x["id"], int) else 0, reverse=True)
    return jsonify(results)


@mindset_bp.route("/api/nominations", methods=["POST"])
@login_required
def api_submit_nomination():
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    nominee = data.get("nominee_name", "").strip()
    mindset_value = data.get("mindset_value", "").strip()
    reason = data.get("nomination_reason", "").strip()
    if not nominee:
        return jsonify({"error": "Please select a nominee."}), 400
    if not mindset_value:
        return jsonify({"error": "Please select a mindset value."}), 400
    if not reason:
        return jsonify({"error": "Please provide a nomination reason."}), 400

    user = session.get("user", {})

    fields = {
        _COL_NOMINEE:   nominee,
        _COL_POSITION:  data.get("nominee_position", "").strip(),
        _COL_LOCATION:  data.get("nominee_property", "").strip(),
        _COL_MINDSET:   mindset_value,
        _COL_COMMENTS:  reason,
        _COL_SUBMITTER: user.get("name", "Unknown"),
    }

    try:
        from graph_client import create_item
        site_id, list_id = _sp()
        create_item(site_id, list_id, fields)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    except Exception as exc:
        return jsonify({"error": f"SharePoint error: {exc}"}), 500

    return jsonify({"success": True, "message": "Nomination submitted successfully."})


@mindset_bp.route("/api/admins", methods=["GET"])
@login_required
def api_admins():
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin access required"}), 403
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    cur = conn.execute(
        "SELECT ID, ADMIN_EMAIL, DATE_CREATED FROM dbo.APP_ADMINS WHERE APP_ID = 24 ORDER BY ID"
    )
    results = []
    for r in cur.fetchall():
        results.append({
            "id": r[0],
            "email": r[1],
            "date_created": r[2].strftime("%m/%d/%Y") if r[2] else None,
        })
    return jsonify(results)


@mindset_bp.route("/api/admins", methods=["POST"])
@login_required
def api_add_admin():
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin access required"}), 403
    data = request.get_json()
    email = data.get("email", "").strip().lower()
    if not email:
        return jsonify({"error": "Email required."}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    cur = conn.execute(
        "SELECT COUNT(*) FROM dbo.APP_ADMINS WHERE APP_ID = 24 AND LOWER(ADMIN_EMAIL) = ?",
        [email]
    )
    if cur.fetchone()[0] > 0:
        return jsonify({"error": "Already an admin."}), 400
    conn.execute(
        "INSERT INTO dbo.APP_ADMINS (APP_ID, APP_NAME, ADMIN_EMAIL, DATE_CREATED) VALUES (?, ?, ?, ?)",
        [24, "Mindset Award Nomination", email, datetime.now()]
    )
    return jsonify({"success": True})


@mindset_bp.route("/api/admins/<int:admin_id>", methods=["DELETE"])
@login_required
def api_remove_admin(admin_id):
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin access required"}), 403
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    conn.execute("DELETE FROM dbo.APP_ADMINS WHERE ID = ? AND APP_ID = 24", [admin_id])
    return jsonify({"success": True})
