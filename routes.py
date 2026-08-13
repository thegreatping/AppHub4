"""Main application routes."""
import json
from flask import Blueprint, render_template, session, jsonify, request, redirect
from auth import login_required
from modules import MODULES, get_module, get_visible_modules, APP_ID_MAP
from security import resolve_access, get_employee_info, get_all_active_employees
from config import APP_VERSION
import sys
from helpers import load_env, SafeConnection

_env = None

def _get_env():
    global _env
    if _env is None:
        _env = load_env()
    return _env

main_bp = Blueprint("main", __name__)


def _get_user_modules():
    """Get the current user's allowed modules (respects impersonation)."""
    return session.get("user_modules", [])


def _get_template_context(active_module=None):
    """Build common template context."""
    user_modules = _get_user_modules()
    # Map numeric App_IDs from session to string module IDs used in MODULES
    allowed_string_ids = set()
    for m in user_modules:
        app_id = m["id"]  # numeric App_ID from resolve_access
        string_id = APP_ID_MAP.get(app_id)
        if string_id:
            allowed_string_ids.add(string_id)
    
    # Always include rent_forecasting_2 regardless of DB module permissions
    _always_visible = {"rent_forecasting_2"}
    visible = [m for m in MODULES if m["id"] in allowed_string_ids or m["id"] in _always_visible] if user_modules else MODULES
    
    if not active_module and visible:
        active_module = visible[0]["id"]

    return {
        "modules": visible,
        "active_module": active_module,
        "user": session.get("user", {}),
        "is_dev_mode": session.get("is_dev_mode", False),
        "is_developer": session.get("is_developer", False),
        "is_impersonating": session.get("is_impersonating", False),
        "impersonating_user": session.get("impersonating_user", None),
        "version": APP_VERSION,
    }


@main_bp.route("/")
@login_required
def index():
    """Render the dashboard landing page."""
    ctx = _get_template_context(active_module="dashboard")
    return render_template("dashboard.html", **ctx)


@main_bp.route("/module/<module_id>")
@login_required
def module(module_id):
    """Render a specific module."""
    mod = get_module(module_id)
    if not mod:
        return "Module not found", 404

    # If it's a native Flask module, render its template
    if mod["type"] == "flask" and mod["route"]:
        return redirect(mod["route"])

    ctx = _get_template_context(active_module=module_id)
    return render_template("shell.html", **ctx)


@main_bp.route("/api/toggle-dev-mode", methods=["POST"])
@login_required
def toggle_dev_mode():
    """Toggle developer mode. Only developers can use this."""
    if not session.get("is_developer"):
        return jsonify({"error": "unauthorized"}), 403
    session["is_dev_mode"] = not session.get("is_dev_mode", False)
    # If turning off dev mode, also stop impersonation
    if not session["is_dev_mode"] and session.get("is_impersonating"):
        _stop_impersonation()
    return jsonify({"dev_mode": session["is_dev_mode"]})


@main_bp.route("/api/impersonate", methods=["POST"])
@login_required
def impersonate():
    """Start impersonating another user. Developer-only."""
    if not session.get("is_developer") or not session.get("is_dev_mode"):
        return jsonify({"error": "unauthorized"}), 403

    data = request.get_json()
    target_email = data.get("email", "").strip().lower()
    if not target_email:
        return jsonify({"error": "email required"}), 400

    # Look up the target employee
    emp = get_employee_info(target_email)
    if not emp:
        return jsonify({"error": "employee not found"}), 404

    # Resolve their access
    access = resolve_access(emp["title_group"], target_email)

    # Store impersonation state (preserve real user info)
    if not session.get("is_impersonating"):
        session["real_user"] = session.get("user")
        session["real_modules"] = session.get("user_modules")

    session["is_impersonating"] = True
    session["impersonating_user"] = {
        "name": emp["name"],
        "email": emp["email"],
        "title_group": emp["title_group"],
        "property": emp["property"],
    }
    session["user_modules"] = [
        {"id": m["id"], "name": m["name"], "access": m["access"]}
        for m in access["modules"]
    ]

    return jsonify({
        "success": True,
        "impersonating": emp["name"],
        "module_count": len(access["modules"]),
    })


@main_bp.route("/api/stop-impersonation", methods=["POST"])
@login_required
def stop_impersonation():
    """Stop impersonating and restore real user."""
    if not session.get("is_developer"):
        return jsonify({"error": "unauthorized"}), 403
    _stop_impersonation()
    return jsonify({"success": True})


@main_bp.route("/api/employees")
@login_required
def employees_list():
    """Get list of active employees for impersonation dropdown. Developer-only."""
    if not session.get("is_developer") or not session.get("is_dev_mode"):
        return jsonify({"error": "unauthorized"}), 403
    employees = get_all_active_employees()
    return jsonify(employees)


def _stop_impersonation():
    """Restore real user session."""
    session["is_impersonating"] = False
    session["impersonating_user"] = None
    if session.get("real_user"):
        session["user_modules"] = session.get("real_modules")
    session.pop("real_user", None)
    session.pop("real_modules", None)


# ── Theme Settings (server-side, per-app per-theme) ───────────────────────────

def _ensure_theme_table(conn):
    """Create APPHUB_THEME_SETTINGS if it doesn't exist."""
    conn.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='APPHUB_THEME_SETTINGS'
        )
        CREATE TABLE dbo.APPHUB_THEME_SETTINGS (
            app_id       NVARCHAR(100) NOT NULL,
            theme        NVARCHAR(20)  NOT NULL,
            overrides    NVARCHAR(MAX) NOT NULL DEFAULT '{}',
            updated_by   NVARCHAR(200),
            updated_at   DATETIME2 DEFAULT GETDATE(),
            PRIMARY KEY (app_id, theme)
        )
    """)


@main_bp.route("/api/theme-settings/<app_id>")
@login_required
def get_theme_settings(app_id):
    """Return saved theme overrides for an app. {dark:{...}, medium:{...}, light:{...}}"""
    try:
        env = _get_env()
        conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
        _ensure_theme_table(conn)
        rows = conn.fetchall(
            "SELECT theme, overrides FROM dbo.APPHUB_THEME_SETTINGS WHERE app_id = ?",
            (app_id,)
        )
        result = {}
        for r in rows:
            try:
                result[r["theme"]] = json.loads(r["overrides"] or "{}")
            except Exception:
                result[r["theme"]] = {}
        return jsonify(result)
    except Exception:
        return jsonify({}), 200  # fail silently — don't break the page


@main_bp.route("/api/theme-settings", methods=["POST"])
@login_required
def save_theme_settings():
    """Save theme overrides for an app. Developer-only."""
    if not session.get("is_developer"):
        return jsonify({"error": "unauthorized"}), 403
    data = request.get_json() or {}
    app_id    = (data.get("app_id") or "").strip()[:100]
    theme     = (data.get("theme") or "").strip()
    overrides = data.get("overrides") or {}
    if not app_id or theme not in ("dark", "medium", "light"):
        return jsonify({"error": "invalid params"}), 400
    # Only allow known CSS var names to prevent injection
    safe_overrides = {k: v for k, v in overrides.items()
                      if k.startswith("--") and len(k) < 60 and len(str(v)) < 30}
    overrides_json = json.dumps(safe_overrides)
    user_email = (session.get("user") or {}).get("email", "unknown")
    try:
        env = _get_env()
        conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
        _ensure_theme_table(conn)
        conn.execute("""
            MERGE dbo.APPHUB_THEME_SETTINGS AS tgt
            USING (SELECT ? AS app_id, ? AS theme) AS src
                ON tgt.app_id = src.app_id AND tgt.theme = src.theme
            WHEN MATCHED THEN
                UPDATE SET overrides=?, updated_by=?, updated_at=GETDATE()
            WHEN NOT MATCHED THEN
                INSERT (app_id, theme, overrides, updated_by)
                VALUES (?, ?, ?, ?);
        """, (app_id, theme, overrides_json, user_email, app_id, theme, overrides_json, user_email))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
