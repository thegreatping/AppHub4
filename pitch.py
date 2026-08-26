"""The Pitch Workflow module.

Employees submit business improvement ideas. Admins review submissions.

Data source : SharePoint list on peakcampus.sharepoint.com/sites/BaseCampApps
List GUID   : a9f9cbd2-b00b-4f70-ba5a-7eb3c77aaa39
APP_ID      : 26

SP columns  : Name, Email, Property_x002f_Location, Location (=Position),
              Ideaforimprovement, Reviewed_x003f_, Reviewed_By, Reviewed_Date,
              Review_Comments, Reviewed_Email, Created, Modified, Attachments
"""
from flask import Blueprint, render_template, session, jsonify, request
from auth import login_required
from nav import build_nav_modules
from helpers import load_env, SafeConnection

pitch_bp = Blueprint("pitch", __name__, url_prefix="/pitch")

APP_ID       = 26
APP_NAME     = "The Pitch Workflow"
SP_SITE_PATH = "peakcampus.sharepoint.com:/sites/BaseCampApps"
SP_LIST_ID   = "a9f9cbd2-b00b-4f70-ba5a-7eb3c77aaa39"


def _sp():
    from graph_client import get_site_id
    return get_site_id(SP_SITE_PATH), SP_LIST_ID


def _is_admin(email: str) -> bool:
    try:
        conn = SafeConnection(load_env(), "DB_APP_SUPPORT", None, direct=True)
        return bool(conn.fetchall(
            "SELECT 1 FROM dbo.APP_ADMINS WHERE APP_ID=? AND LOWER(ADMIN_EMAIL)=?",
            (APP_ID, email.lower())
        ))
    except Exception:
        return False


def _ctx(**kw):
    user     = session.get("user", {})
    email    = user.get("email", "")
    is_dev   = session.get("is_developer", False)
    is_admin = is_dev or _is_admin(email)
    d = dict(
        modules=build_nav_modules(),
        active_module="the_pitch_workflow",
        user=user, is_developer=is_dev, is_admin=is_admin,
        app_name=APP_NAME,
    )
    d.update(kw)
    return d


def _normalize(row: dict) -> dict:
    """Map raw SP field names to stable API keys."""
    reviewed = row.get("Reviewed_x003f_", False)
    return {
        "id":               row.get("_item_id") or row.get("id", ""),
        "name":             row.get("Name") or "",
        "email":            row.get("Email") or "",
        "property_location": row.get("Property_x002f_Location") or "",
        "position":         row.get("Location") or "",
        "idea":             row.get("Ideaforimprovement") or "",
        "reviewed":         bool(reviewed),
        "status":           "Reviewed" if reviewed else "Pending Review",
        "reviewed_by":      row.get("Reviewed_By") or "",
        "reviewed_date":    row.get("Reviewed_Date") or "",
        "review_comments":  row.get("Review_Comments") or "",
        "reviewed_email":   row.get("Reviewed_Email") or "",
        "has_attachments":  bool(row.get("Attachments", False)),
        "created":          row.get("Created") or "",
        "modified":         row.get("Modified") or "",
    }


# -- Main page -----------------------------------------------------------------

@pitch_bp.route("/")
@login_required
def index():
    return render_template("pitch.html", **_ctx())


# -- API: list pitches ---------------------------------------------------------

@pitch_bp.route("/api/pitches")
@login_required
def api_list():
    user     = session.get("user", {})
    email    = user.get("email", "").lower()
    is_admin = session.get("is_developer", False) or _is_admin(email)

    reviewed = request.args.get("reviewed", "").strip()  # "true"/"false"/""
    mine     = request.args.get("mine", "").strip()       # "1" = only my pitches

    try:
        site_id, list_id = _sp()
        from graph_client import list_items
        rows = list_items(site_id, list_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    result = [_normalize(r) for r in rows]

    if reviewed == "true":
        result = [r for r in result if r["reviewed"]]
    elif reviewed == "false":
        result = [r for r in result if not r["reviewed"]]

    if mine == "1" or not is_admin:
        result = [r for r in result if r["email"].lower() == email]

    result.sort(key=lambda r: r["created"], reverse=True)
    return jsonify(result)


# -- API: get single pitch -----------------------------------------------------

@pitch_bp.route("/api/pitch/<item_id>")
@login_required
def api_get(item_id):
    try:
        site_id, list_id = _sp()
        from graph_client import _headers
        import requests
        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items/{item_id}?$expand=fields"
        r = requests.get(url, headers=_headers(), timeout=10)
        if r.status_code == 404:
            return jsonify({"error": "Not found"}), 404
        r.raise_for_status()
        fields = r.json().get("fields", {})
        fields["_item_id"] = item_id
        return jsonify(_normalize(fields))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -- API: submit new pitch -----------------------------------------------------

@pitch_bp.route("/api/pitch", methods=["POST"])
@login_required
def api_submit():
    user     = session.get("user", {})
    email    = user.get("email", "")
    name     = user.get("name", email)

    idea     = (request.form.get("idea") or "").strip()
    prop     = (request.form.get("property_location") or "").strip()
    position = (request.form.get("position") or "").strip()

    if not idea:
        return jsonify({"error": "Idea is required."}), 400

    fields = {
        "Name":                     name,
        "Email":                    email,
        "Property_x002f_Location":  prop,
        "Location":                 position,
        "Ideaforimprovement":       idea,
        "Reviewed_x003f_":          False,
    }
    try:
        site_id, list_id = _sp()
        from graph_client import create_item
        created = create_item(site_id, list_id, fields)
        return jsonify({"id": created.get("_item_id", "")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -- API: review / update pitch (admin) ----------------------------------------

@pitch_bp.route("/api/pitch/<item_id>", methods=["PATCH"])
@login_required
def api_update(item_id):
    user   = session.get("user", {})
    email  = user.get("email", "")
    is_dev = session.get("is_developer", False)
    if not is_dev and not _is_admin(email):
        return jsonify({"error": "Admin access required."}), 403

    data = request.get_json(force=True) or {}
    fields = {}
    if "reviewed" in data:
        fields["Reviewed_x003f_"] = bool(data["reviewed"])
    if "review_comments" in data:
        fields["Review_Comments"] = data["review_comments"]
    if fields.get("Reviewed_x003f_"):
        fields["Reviewed_By"]    = user.get("name", email)
        fields["Reviewed_Email"] = email
        from datetime import datetime
        fields["Reviewed_Date"]  = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    if not fields:
        return jsonify({"error": "Nothing to update."}), 400

    try:
        site_id, list_id = _sp()
        from graph_client import update_item
        update_item(site_id, list_id, item_id, fields)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -- API: delete pitch (admin) -------------------------------------------------

@pitch_bp.route("/api/pitch/<item_id>", methods=["DELETE"])
@login_required
def api_delete(item_id):
    user   = session.get("user", {})
    email  = user.get("email", "")
    is_dev = session.get("is_developer", False)
    if not is_dev and not _is_admin(email):
        return jsonify({"error": "Admin access required."}), 403
    try:
        site_id, list_id = _sp()
        from graph_client import delete_item
        delete_item(site_id, list_id, item_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
