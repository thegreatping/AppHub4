"""Peak Link Idea module — submit and track ideas through the Peak Link program.

Data store: SharePoint list on peakcampus.sharepoint.com/sites/BaseCampApps
List GUID : 8524acb0-c727-46a2-bc90-c5160b4d5c98
Auth      : Microsoft Graph API (MSAL client-credentials flow)

DEPLOY NOTE: The Azure AD app registration must have the
  Sites.ReadWrite.All  (application permission)
consented before this module can read/write SharePoint data.
"""
from flask import Blueprint, render_template, session, jsonify, request
from auth import login_required
from modules import MODULES, APP_ID_MAP
from nav import build_nav_modules
import sys
from helpers import load_env, SafeConnection
from datetime import datetime

peak_link_bp = Blueprint("peak_link", __name__, url_prefix="/peak-link")

# ── Constants ────────────────────────────────────────────────────────────────────
APP_ID = 25
APP_NAME = "Peak Link Idea"
SP_SITE_PATH = "peakcampus.sharepoint.com:/sites/BaseCampApps"
SP_LIST_ID   = "8524acb0-c727-46a2-bc90-c5160b4d5c98"

# SharePoint choice field values — internal name: SuggestionType
# Confirmed from live list column definition 2026-07-23.
SUGGESTION_TYPES = [
    "Spotlight Nomination",
    "Social Series",
    "Town Hall Topics",
    "Employee Resource Groups",
    "Newsletter Spotlights",
    "Other",
]

# SharePoint internal column names (Graph API uses these, NOT display names)
_COL_TYPE    = "SuggestionType"                       # choice
_COL_DETAILS = "SuggestionDetailsand_x002f_orSpo"     # text (display: Suggestion_Details_and/or_Spotlight_Team_Member_Nomination)
_COL_NAME    = "Employee_Name_Full"                   # text
_COL_LOC     = "Property_Location"                    # text
_COL_CODE    = "Employee_Code"                        # text (display: Submitted_by_Employee_Code)

_env = None


def _get_env():
    global _env
    if _env is None:
        _env = load_env()
    return _env


def _require_access():
    """Check that the current user has access to Peak Link (app_id=25)."""
    if session.get("is_developer"):
        return None
    user_modules = session.get("user_modules", [])
    for m in user_modules:
        if m["id"] == APP_ID:
            return None
    return jsonify({"error": "unauthorized"}), 403


def _is_admin():
    """Check if current user is a Peak Link admin."""
    if session.get("is_developer"):
        return True
    user = session.get("user", {})
    email = user.get("email", "").lower()
    if not email:
        return False
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    cur = conn.execute(
        "SELECT COUNT(*) FROM dbo.APP_ADMINS WHERE APP_ID = ? AND LOWER(ADMIN_EMAIL) = ?",
        [APP_ID, email]
    )
    return cur.fetchone()[0] > 0


def _get_shell_context():
    """Build standard shell template context."""
    from config import APP_VERSION
    visible = build_nav_modules()
    return dict(
        modules=visible,
        active_module="peak_link_idea",
        user=session.get("user", {}),
        is_developer=session.get("is_developer", False),
        is_dev_mode=session.get("is_dev_mode", False),
        is_impersonating=session.get("is_impersonating", False),
        impersonating_user=session.get("impersonating_user", None),
        version=APP_VERSION,
    )


def _sp():
    """Return (site_id, list_id) tuple, resolving site lazily."""
    from graph_client import get_site_id
    return get_site_id(SP_SITE_PATH), SP_LIST_ID


# ─── PAGE ROUTE ──────────────────────────────────────────────────────────────────

@peak_link_bp.route("/")
@login_required
def index():
    check = _require_access()
    if check:
        return check
    ctx = _get_shell_context()
    ctx["is_admin"] = _is_admin()
    return render_template("peak_link.html", **ctx)


# ─── API: SUGGESTION TYPES ───────────────────────────────────────────────────────

@peak_link_bp.route("/api/suggestion-types", methods=["GET"])
@login_required
def api_suggestion_types():
    """Return the Suggestion_Type choice values."""
    check = _require_access()
    if check:
        return check
    return jsonify(SUGGESTION_TYPES)


# ─── API: LOCATIONS ──────────────────────────────────────────────────────────────

@peak_link_bp.route("/api/locations", methods=["GET"])
@login_required
def api_locations():
    """Return property/location list from DB_APP_SUPPORT."""
    check = _require_access()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    cur = conn.execute("""
        SELECT DISTINCT LOCATION_NAME
        FROM dbo.APP_LOCATION_LIST
        WHERE FLAG_ACTIVE = 1
        ORDER BY LOCATION_NAME
    """)
    return jsonify([r[0] for r in cur.fetchall()])


# ─── API: SUBMIT IDEA ────────────────────────────────────────────────────────────

@peak_link_bp.route("/api/submit", methods=["POST"])
@login_required
def api_submit():
    """Submit a new idea to the SharePoint Peak Link list."""
    check = _require_access()
    if check:
        return check

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    suggestion_type = (data.get("suggestion_type") or "").strip()
    details = (data.get("details") or "").strip()

    if not suggestion_type:
        return jsonify({"error": "Suggestion type is required"}), 400
    if not details:
        return jsonify({"error": "Details are required"}), 400
    if suggestion_type not in SUGGESTION_TYPES:
        return jsonify({"error": "Invalid suggestion type"}), 400
    if len(details) > 2048:
        return jsonify({"error": "Details must be 2048 characters or fewer"}), 400

    user = session.get("user", {})
    employee_name = user.get("name", "")

    user_code = user.get("employee_code", "") or user.get("username", "") or ""

    fields = {
        _COL_TYPE:    suggestion_type,
        _COL_DETAILS: details,
        _COL_NAME:    employee_name,
        _COL_CODE:    user_code,
    }

    location = (data.get("location") or "").strip()
    if location:
        fields[_COL_LOC] = location

    try:
        from graph_client import create_item
        site_id, list_id = _sp()
        create_item(site_id, list_id, fields)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    except Exception as exc:
        return jsonify({"error": f"SharePoint error: {exc}"}), 500

    return jsonify({"success": True, "message": "Idea submitted successfully."})


# ─── API: ALL SUBMISSIONS (admin) ────────────────────────────────────────────────

@peak_link_bp.route("/api/submissions", methods=["GET"])
@login_required
def api_submissions():
    """Return all submissions from SharePoint (admin only)."""
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
            "id":              row.get("_item_id", ""),
            "suggestion_type": row.get(_COL_TYPE, ""),
            "details":         row.get(_COL_DETAILS, ""),
            "location":        row.get(_COL_LOC, ""),
            "employee":        row.get(_COL_NAME, ""),
            "submitted":       row.get("Created", ""),   # auto-populated by SharePoint
        })

    # Sort newest first
    results.sort(key=lambda x: x["submitted"], reverse=True)
    return jsonify(results)


# ─── API: IS ADMIN ───────────────────────────────────────────────────────────────

@peak_link_bp.route("/api/is_admin", methods=["GET"])
@login_required
def api_is_admin():
    check = _require_access()
    if check:
        return check
    return jsonify({"is_admin": _is_admin()})


# ─── API: ADMINS ─────────────────────────────────────────────────────────────────

@peak_link_bp.route("/api/admins", methods=["GET"])
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
        FROM dbo.APP_ADMINS
        WHERE APP_ID = ?
        ORDER BY ID
    """, [APP_ID])
    results = []
    for r in cur.fetchall():
        results.append({
            "id":           r[0],
            "email":        r[1],
            "date_created": r[2].strftime("%Y-%m-%d") if r[2] else None,
        })
    return jsonify(results)


@peak_link_bp.route("/api/admins", methods=["POST"])
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
    cur = conn.execute(
        "SELECT COUNT(*) FROM dbo.APP_ADMINS WHERE APP_ID = ? AND LOWER(ADMIN_EMAIL) = ?",
        [APP_ID, email]
    )
    if cur.fetchone()[0] > 0:
        return jsonify({"error": "Admin already exists"}), 409
    conn.execute("""
        INSERT INTO dbo.APP_ADMINS (APP_ID, APP_NAME, ADMIN_EMAIL, DATE_CREATED)
        VALUES (?, ?, ?, ?)
    """, [APP_ID, APP_NAME, email, datetime.now()])
    return jsonify({"success": True, "message": "Admin added."})


@peak_link_bp.route("/api/admins/<int:admin_id>", methods=["DELETE"])
@login_required
def api_remove_admin(admin_id):
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin access required"}), 403
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    conn.execute("DELETE FROM dbo.APP_ADMINS WHERE ID = ? AND APP_ID = ?", [admin_id, APP_ID])
    return jsonify({"success": True, "message": "Admin removed."})
