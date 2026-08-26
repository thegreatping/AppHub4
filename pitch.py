"""The Pitch Workflow module.

Employees submit business improvement ideas ('pitches') with supporting documents.
Admins review submissions and move them through an approval workflow.

Data source : DB_APP_SUPPORT.dbo.THE_PITCH
APP_ID      : 26

Status flow : Submitted -> Under Review -> Approved | Rejected | On Hold
Documents   : Up to 3 files stored as varbinary(MAX) in the DB row
"""
from flask import Blueprint, render_template, session, jsonify, request, send_file
from auth import login_required
from nav import build_nav_modules
from helpers import load_env, SafeConnection
from datetime import datetime, date
import io

pitch_bp = Blueprint("pitch", __name__, url_prefix="/pitch")

APP_ID   = 26
APP_NAME = "The Pitch Workflow"

CATEGORIES = [
    "Cost Savings",
    "Revenue Growth",
    "Process Improvement",
    "Resident Experience",
    "Team Culture",
    "Technology",
    "Other",
]

STATUSES = ["Submitted", "Under Review", "Approved", "Rejected", "On Hold"]

STATUS_COLOR = {
    "Submitted":    "cyan",
    "Under Review": "gold",
    "Approved":     "green",
    "Rejected":     "red",
    "On Hold":      "gray",
}


def _get_env():
    return load_env()


def _is_admin(email: str) -> bool:
    try:
        conn = SafeConnection(_get_env(), "DB_APP_SUPPORT", None, direct=True)
        rows = conn.fetchall(
            "SELECT 1 FROM dbo.APP_ADMINS WHERE APP_ID=? AND LOWER(ADMIN_EMAIL)=?",
            (APP_ID, email.lower())
        )
        return bool(rows)
    except Exception:
        return False


def _get_template_context(**kwargs):
    user      = session.get("user", {})
    email     = user.get("email", "")
    is_dev    = session.get("is_developer", False)
    is_admin  = is_dev or _is_admin(email)
    visible   = build_nav_modules()
    ctx = dict(
        modules=visible,
        active_module="the_pitch_workflow",
        user=user,
        is_developer=is_dev,
        is_admin=is_admin,
        app_name=APP_NAME,
        categories=CATEGORIES,
        statuses=STATUSES,
    )
    ctx.update(kwargs)
    return ctx


def _row_to_dict(r, include_docs=False):
    keys = ["ID","COMMENTS","DATE_CREATED","DOCUMENT_NAME_1","DOCUMENT_NAME_2","DOCUMENT_NAME_3",
            "EMPLOYEE_CODE","EMPLOYEE_NAME_FULL","PROPERTY_OR_LOCATION",
            "PITCH_TITLE","PITCH_CATEGORY","PITCH_STATUS","REVIEW_COMMENTS",
            "REVIEWED_BY","DATE_MODIFIED","MODIFIED_BY"]
    # exclude varbinary columns unless requested
    if include_docs:
        keys = ["ID","COMMENTS","DATE_CREATED","DOCUMENT_1","DOCUMENT_2","DOCUMENT_3",
                "DOCUMENT_NAME_1","DOCUMENT_NAME_2","DOCUMENT_NAME_3",
                "EMPLOYEE_CODE","EMPLOYEE_NAME_FULL","PROPERTY_OR_LOCATION",
                "PITCH_TITLE","PITCH_CATEGORY","PITCH_STATUS","REVIEW_COMMENTS",
                "REVIEWED_BY","DATE_MODIFIED","MODIFIED_BY"]
    d = {}
    for k, v in zip(keys, r):
        if isinstance(v, (datetime, date)):
            d[k] = v.strftime("%Y-%m-%d")
        elif isinstance(v, (bytes, bytearray)):
            d[k] = bool(v)   # just flag presence; never serialize raw bytes
        else:
            d[k] = v
    return d


# ── Main page ─────────────────────────────────────────────────────────────────

@pitch_bp.route("/")
@login_required
def index():
    return render_template("pitch.html", **_get_template_context())


# ── API: list ─────────────────────────────────────────────────────────────────

@pitch_bp.route("/api/pitches")
@login_required
def api_list():
    user     = session.get("user", {})
    email    = user.get("email", "")
    is_admin = session.get("is_developer", False) or _is_admin(email)

    status   = request.args.get("status", "").strip()
    category = request.args.get("category", "").strip()
    mine     = request.args.get("mine", "").strip()  # "1" = only my pitches

    where, params = [], []
    if status:
        where.append("PITCH_STATUS = ?"); params.append(status)
    if category:
        where.append("PITCH_CATEGORY = ?"); params.append(category)
    if mine == "1" or not is_admin:
        # non-admins only see their own
        where.append("LOWER(MODIFIED_BY) = ?"); params.append(email.lower())

    w = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT ID, PITCH_TITLE, PITCH_CATEGORY, PITCH_STATUS,
               EMPLOYEE_NAME_FULL, PROPERTY_OR_LOCATION,
               DATE_CREATED, DOCUMENT_NAME_1, DOCUMENT_NAME_2, DOCUMENT_NAME_3,
               REVIEW_COMMENTS, REVIEWED_BY, DATE_MODIFIED, MODIFIED_BY,
               COMMENTS
        FROM dbo.THE_PITCH
        {w}
        ORDER BY ID DESC
    """
    conn = SafeConnection(_get_env(), "DB_APP_SUPPORT", None, direct=True)
    rows = conn.fetchall(sql, params)
    keys = ["ID","PITCH_TITLE","PITCH_CATEGORY","PITCH_STATUS",
            "EMPLOYEE_NAME_FULL","PROPERTY_OR_LOCATION",
            "DATE_CREATED","DOCUMENT_NAME_1","DOCUMENT_NAME_2","DOCUMENT_NAME_3",
            "REVIEW_COMMENTS","REVIEWED_BY","DATE_MODIFIED","MODIFIED_BY","COMMENTS"]
    return jsonify([dict(zip(keys, r)) for r in rows])


# ── API: get single ───────────────────────────────────────────────────────────

@pitch_bp.route("/api/pitch/<int:pitch_id>")
@login_required
def api_get(pitch_id):
    conn = SafeConnection(_get_env(), "DB_APP_SUPPORT", None, direct=True)
    rows = conn.fetchall("""
        SELECT ID, PITCH_TITLE, PITCH_CATEGORY, PITCH_STATUS,
               EMPLOYEE_NAME_FULL, EMPLOYEE_CODE, PROPERTY_OR_LOCATION,
               DATE_CREATED, COMMENTS,
               DOCUMENT_NAME_1, DOCUMENT_NAME_2, DOCUMENT_NAME_3,
               REVIEW_COMMENTS, REVIEWED_BY, DATE_MODIFIED, MODIFIED_BY,
               CASE WHEN DOCUMENT_1 IS NOT NULL THEN 1 ELSE 0 END,
               CASE WHEN DOCUMENT_2 IS NOT NULL THEN 1 ELSE 0 END,
               CASE WHEN DOCUMENT_3 IS NOT NULL THEN 1 ELSE 0 END
        FROM dbo.THE_PITCH WHERE ID=?
    """, (pitch_id,))
    if not rows:
        return jsonify({"error": "not found"}), 404
    r = rows[0]
    keys = ["ID","PITCH_TITLE","PITCH_CATEGORY","PITCH_STATUS",
            "EMPLOYEE_NAME_FULL","EMPLOYEE_CODE","PROPERTY_OR_LOCATION",
            "DATE_CREATED","COMMENTS",
            "DOCUMENT_NAME_1","DOCUMENT_NAME_2","DOCUMENT_NAME_3",
            "REVIEW_COMMENTS","REVIEWED_BY","DATE_MODIFIED","MODIFIED_BY",
            "has_doc_1","has_doc_2","has_doc_3"]
    return jsonify(dict(zip(keys, r)))


# ── API: submit new pitch ─────────────────────────────────────────────────────

@pitch_bp.route("/api/pitch", methods=["POST"])
@login_required
def api_submit():
    user  = session.get("user", {})
    email = user.get("email", "")
    name  = user.get("name", email)

    title    = (request.form.get("title") or "").strip()
    category = (request.form.get("category") or "").strip()
    prop     = (request.form.get("property") or "").strip()
    comments = (request.form.get("comments") or "").strip()

    if not title or not comments:
        return jsonify({"error": "Title and description are required"}), 400
    if category not in CATEGORIES:
        category = "Other"

    today = int(datetime.now().strftime("%Y%m%d"))

    # Up to 3 file attachments
    doc_data, doc_names = [None, None, None], [None, None, None]
    for i in range(1, 4):
        f = request.files.get(f"doc_{i}")
        if f and f.filename:
            doc_data[i-1]  = f.read()
            doc_names[i-1] = f.filename[:255]

    conn = SafeConnection(_get_env(), "DB_APP_SUPPORT", None, direct=True)
    conn.execute("""
        INSERT INTO dbo.THE_PITCH
            (PITCH_TITLE, PITCH_CATEGORY, PITCH_STATUS, COMMENTS,
             EMPLOYEE_NAME_FULL, PROPERTY_OR_LOCATION,
             DOCUMENT_1, DOCUMENT_2, DOCUMENT_3,
             DOCUMENT_NAME_1, DOCUMENT_NAME_2, DOCUMENT_NAME_3,
             DATE_CREATED, MODIFIED_BY, DATE_MODIFIED)
        VALUES (?,?,?,?, ?,?, ?,?,?, ?,?,?, ?,?,?)
    """, (title, category, "Submitted", comments,
          name, prop,
          doc_data[0], doc_data[1], doc_data[2],
          doc_names[0], doc_names[1], doc_names[2],
          today, email, today))

    new_id = conn.fetchall("SELECT MAX(ID) FROM dbo.THE_PITCH")[0][0]
    return jsonify({"ok": True, "ID": new_id})


# ── API: admin update status / review comments ────────────────────────────────

@pitch_bp.route("/api/pitch/<int:pitch_id>", methods=["PATCH"])
@login_required
def api_update(pitch_id):
    user  = session.get("user", {})
    email = user.get("email", "")
    is_admin = session.get("is_developer", False) or _is_admin(email)
    if not is_admin:
        return jsonify({"error": "unauthorized"}), 403

    data   = request.get_json() or {}
    status = (data.get("PITCH_STATUS") or "").strip()
    review = (data.get("REVIEW_COMMENTS") or "").strip() or None

    if status and status not in STATUSES:
        return jsonify({"error": "invalid status"}), 400

    today = int(datetime.now().strftime("%Y%m%d"))
    conn  = SafeConnection(_get_env(), "DB_APP_SUPPORT", None, direct=True)

    sets, params = [], []
    if status:
        sets.append("PITCH_STATUS=?"); params.append(status)
    if review is not None:
        sets.append("REVIEW_COMMENTS=?"); params.append(review)
    sets.append("REVIEWED_BY=?");   params.append(email)
    sets.append("DATE_MODIFIED=?"); params.append(today)

    conn.execute(
        f"UPDATE dbo.THE_PITCH SET {','.join(sets)} WHERE ID=?",
        params + [pitch_id]
    )
    return jsonify({"ok": True})


# ── API: delete ───────────────────────────────────────────────────────────────

@pitch_bp.route("/api/pitch/<int:pitch_id>", methods=["DELETE"])
@login_required
def api_delete(pitch_id):
    user  = session.get("user", {})
    email = user.get("email", "")
    is_admin = session.get("is_developer", False) or _is_admin(email)
    if not is_admin:
        return jsonify({"error": "unauthorized"}), 403
    conn = SafeConnection(_get_env(), "DB_APP_SUPPORT", None, direct=True)
    conn.execute("DELETE FROM dbo.THE_PITCH WHERE ID=?", (pitch_id,))
    return jsonify({"ok": True})


# ── Download attachment ───────────────────────────────────────────────────────

@pitch_bp.route("/api/pitch/<int:pitch_id>/doc/<int:doc_num>")
@login_required
def api_doc(pitch_id, doc_num):
    if doc_num not in (1, 2, 3):
        return "invalid", 400
    conn  = SafeConnection(_get_env(), "DB_APP_SUPPORT", None, direct=True)
    rows  = conn.fetchall(
        f"SELECT DOCUMENT_{doc_num}, DOCUMENT_NAME_{doc_num} FROM dbo.THE_PITCH WHERE ID=?",
        (pitch_id,)
    )
    if not rows or not rows[0][0]:
        return "not found", 404
    data, name = rows[0]
    return send_file(io.BytesIO(data), download_name=name or f"document_{doc_num}", as_attachment=True)
