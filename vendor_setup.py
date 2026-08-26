"""Vendor Setup Form module.

Submit and manage vendor onboarding requests.

Data source : DB_APP_SUPPORT.dbo.VENDOR_SETUP_REQUEST
APP_ID      : 17

Statuses    : Pending, Under Review, Approved, Rejected, On Hold
"""
from flask import Blueprint, render_template, session, jsonify, request, send_file
from auth import login_required
from modules import MODULES, APP_ID_MAP
from nav import build_nav_modules
from helpers import load_env, SafeConnection
from datetime import datetime, date
import io

vendor_setup_bp = Blueprint("vendor_setup", __name__, url_prefix="/vendor-setup")

APP_ID   = 17
APP_NAME = "Vendor Setup Form"

VENDOR_TYPES   = ["Maintenance", "Landscaping", "Cleaning", "Pest Control", "Security",
                  "HVAC", "Plumbing", "Electrical", "IT / Technology", "Marketing",
                  "Legal / Compliance", "Staffing", "Construction", "Utilities", "Other"]
BUSINESS_TYPES = ["LLC", "Corporation", "S-Corporation", "Sole Proprietor",
                  "Partnership", "Non-Profit", "Government", "Other"]
STATUSES       = ["Pending", "Under Review", "Approved", "Rejected", "On Hold"]
PAYMENT_METHODS = ["Check", "ACH"]
ACCT_TYPES     = ["Checking", "Savings"]


def _env():
    return load_env()


def _is_admin(email: str) -> bool:
    try:
        conn = SafeConnection(_env(), "DB_APP_SUPPORT", None, direct=True)
        rows = conn.fetchall(
            "SELECT 1 FROM dbo.APP_ADMINS WHERE APP_ID=? AND LOWER(ADMIN_EMAIL)=?",
            (APP_ID, email.lower())
        )
        return bool(rows)
    except Exception:
        return False


def _row_to_dict(r, cols):
    def _v(val):
        if isinstance(val, (datetime, date)):
            return val.strftime("%Y-%m-%d")
        if isinstance(val, (bytes, bytearray)):
            return bool(val)  # just signal presence, not the bytes
        return val
    return {cols[i]: _v(r[i]) for i in range(len(cols))}


def _ctx(**kwargs):
    user     = session.get("user", {})
    email    = user.get("email", "")
    is_dev   = session.get("is_developer", False)
    is_admin = is_dev or _is_admin(email)
    ctx = dict(
        modules=build_nav_modules(),
        active_module="vendor_setup_form",
        user=user,
        is_developer=is_dev,
        is_admin=is_admin,
        app_name=APP_NAME,
        vendor_types=VENDOR_TYPES,
        business_types=BUSINESS_TYPES,
        statuses=STATUSES,
        payment_methods=PAYMENT_METHODS,
        acct_types=ACCT_TYPES,
    )
    ctx.update(kwargs)
    return ctx


# ── Main page ─────────────────────────────────────────────────────────────────

@vendor_setup_bp.route("/")
@login_required
def index():
    return render_template("vendor_setup.html", **_ctx())


# ── API: list requests ────────────────────────────────────────────────────────

@vendor_setup_bp.route("/api/requests")
@login_required
def api_list():
    user   = session.get("user", {})
    email  = user.get("email", "").lower()
    is_dev = session.get("is_developer", False)
    admin  = is_dev or _is_admin(email)
    mine   = request.args.get("mine", "") == "1"

    status   = request.args.get("status", "").strip()
    vtype    = request.args.get("vtype", "").strip()
    q        = request.args.get("q", "").strip()

    where, params = ["1=1"], []
    if not admin or mine:
        where.append("LOWER(SUBMITTED_BY_EMAIL)=?"); params.append(email)
    if status:
        where.append("STATUS=?"); params.append(status)
    if vtype:
        where.append("VENDOR_TYPE=?"); params.append(vtype)
    if q:
        where.append("(VENDOR_NAME LIKE ? OR PRIMARY_CONTACT LIKE ? OR PROPERTY_NAME LIKE ?)")
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]

    sql = f"""
        SELECT ID, VENDOR_NAME, VENDOR_DBA, VENDOR_TYPE, BUSINESS_TYPE, EIN,
               PRIMARY_CONTACT, CONTACT_PHONE, CONTACT_EMAIL,
               ADDRESS_1, ADDRESS_2, CITY, STATE, ZIP,
               PROPERTY_NAME, PAYMENT_METHOD,
               BANK_NAME, BANK_ACCOUNT_TYPE,
               NOTES, STATUS, SUBMITTED_BY, SUBMITTED_BY_EMAIL,
               DATE_SUBMITTED, DATE_MODIFIED, MODIFIED_BY,
               REVIEW_NOTES, REVIEWED_BY,
               CASE WHEN DOC_W9       IS NOT NULL THEN 1 ELSE 0 END as has_w9,
               CASE WHEN DOC_INSURANCE IS NOT NULL THEN 1 ELSE 0 END as has_insurance,
               CASE WHEN DOC_OTHER    IS NOT NULL THEN 1 ELSE 0 END as has_other,
               DOC_W9_NAME, DOC_INSURANCE_NAME, DOC_OTHER_NAME
        FROM dbo.VENDOR_SETUP_REQUEST
        WHERE {' AND '.join(where)}
        ORDER BY DATE_SUBMITTED DESC
    """
    try:
        conn = SafeConnection(_env(), "DB_APP_SUPPORT", None, direct=True)
        cur  = conn.execute(sql, params if params else None)
        cols = [d[0] for d in cur.description]
        rows = [_row_to_dict(r, cols) for r in cur.fetchall()]
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API: get single request ───────────────────────────────────────────────────

@vendor_setup_bp.route("/api/request/<int:req_id>")
@login_required
def api_get(req_id):
    sql = """
        SELECT ID, VENDOR_NAME, VENDOR_DBA, VENDOR_TYPE, BUSINESS_TYPE, EIN,
               PRIMARY_CONTACT, CONTACT_PHONE, CONTACT_EMAIL,
               ADDRESS_1, ADDRESS_2, CITY, STATE, ZIP,
               PROPERTY_NAME, PAYMENT_METHOD,
               BANK_NAME, BANK_ACCOUNT_TYPE, BANK_ROUTING, BANK_ACCOUNT,
               NOTES, STATUS, SUBMITTED_BY, SUBMITTED_BY_EMAIL,
               DATE_SUBMITTED, DATE_MODIFIED, MODIFIED_BY,
               REVIEW_NOTES, REVIEWED_BY,
               CASE WHEN DOC_W9       IS NOT NULL THEN 1 ELSE 0 END as has_w9,
               CASE WHEN DOC_INSURANCE IS NOT NULL THEN 1 ELSE 0 END as has_insurance,
               CASE WHEN DOC_OTHER    IS NOT NULL THEN 1 ELSE 0 END as has_other,
               DOC_W9_NAME, DOC_INSURANCE_NAME, DOC_OTHER_NAME
        FROM dbo.VENDOR_SETUP_REQUEST WHERE ID=?
    """
    try:
        conn = SafeConnection(_env(), "DB_APP_SUPPORT", None, direct=True)
        cur  = conn.execute(sql, (req_id,))
        cols = [d[0] for d in cur.description]
        row  = cur.fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404
        user   = session.get("user", {})
        email  = user.get("email", "").lower()
        is_dev = session.get("is_developer", False)
        admin  = is_dev or _is_admin(email)
        d = _row_to_dict(row, cols)
        # Redact banking details for non-admins who don't own the request
        if not admin and d.get("SUBMITTED_BY_EMAIL", "").lower() != email:
            return jsonify({"error": "Forbidden"}), 403
        if not admin:
            d.pop("BANK_ROUTING", None)
            d.pop("BANK_ACCOUNT", None)
        return jsonify(d)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API: submit new request ───────────────────────────────────────────────────

@vendor_setup_bp.route("/api/request", methods=["POST"])
@login_required
def api_submit():
    user  = session.get("user", {})
    email = user.get("email", "")
    name  = user.get("name", email)

    vendor_name = (request.form.get("vendor_name") or "").strip()
    if not vendor_name:
        return jsonify({"error": "Vendor name is required."}), 400

    fields = {
        "VENDOR_NAME":        vendor_name,
        "VENDOR_DBA":         (request.form.get("vendor_dba") or "").strip() or None,
        "VENDOR_TYPE":        (request.form.get("vendor_type") or "").strip() or None,
        "BUSINESS_TYPE":      (request.form.get("business_type") or "").strip() or None,
        "EIN":                (request.form.get("ein") or "").strip() or None,
        "PRIMARY_CONTACT":    (request.form.get("primary_contact") or "").strip() or None,
        "CONTACT_PHONE":      (request.form.get("contact_phone") or "").strip() or None,
        "CONTACT_EMAIL":      (request.form.get("contact_email") or "").strip() or None,
        "ADDRESS_1":          (request.form.get("address_1") or "").strip() or None,
        "ADDRESS_2":          (request.form.get("address_2") or "").strip() or None,
        "CITY":               (request.form.get("city") or "").strip() or None,
        "STATE":              (request.form.get("state") or "").strip() or None,
        "ZIP":                (request.form.get("zip") or "").strip() or None,
        "PROPERTY_NAME":      (request.form.get("property_name") or "").strip() or None,
        "PAYMENT_METHOD":     (request.form.get("payment_method") or "").strip() or None,
        "BANK_NAME":          (request.form.get("bank_name") or "").strip() or None,
        "BANK_ACCOUNT_TYPE":  (request.form.get("bank_account_type") or "").strip() or None,
        "BANK_ROUTING":       (request.form.get("bank_routing") or "").strip() or None,
        "BANK_ACCOUNT":       (request.form.get("bank_account") or "").strip() or None,
        "NOTES":              (request.form.get("notes") or "").strip() or None,
        "SUBMITTED_BY":       name,
        "SUBMITTED_BY_EMAIL": email,
    }

    # File attachments
    for slot, col in [("doc_w9", "W9"), ("doc_insurance", "INSURANCE"), ("doc_other", "OTHER")]:
        f = request.files.get(slot)
        if f and f.filename:
            fields[f"DOC_{col}"]      = f.read()
            fields[f"DOC_{col}_NAME"] = f.filename[:255]

    cols   = list(fields.keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_list     = ", ".join(cols)
    sql = f"""
        INSERT INTO dbo.VENDOR_SETUP_REQUEST ({col_list})
        OUTPUT INSERTED.ID
        VALUES ({placeholders})
    """
    try:
        conn = SafeConnection(_env(), "DB_APP_SUPPORT", None, direct=True)
        cur  = conn.execute(sql, list(fields.values()))
        new_id = cur.fetchone()[0]
        return jsonify({"ID": new_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API: update (admin review) ────────────────────────────────────────────────

@vendor_setup_bp.route("/api/request/<int:req_id>", methods=["PATCH"])
@login_required
def api_update(req_id):
    user   = session.get("user", {})
    email  = user.get("email", "")
    is_dev = session.get("is_developer", False)
    if not is_dev and not _is_admin(email):
        return jsonify({"error": "Forbidden"}), 403

    data   = request.get_json(force=True) or {}
    allowed = {"STATUS", "REVIEW_NOTES"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": "Nothing to update"}), 400

    updates["DATE_MODIFIED"] = datetime.now()
    updates["MODIFIED_BY"]   = user.get("name", email)
    updates["REVIEWED_BY"]   = user.get("name", email)

    set_clause = ", ".join(f"{k}=?" for k in updates)
    sql = f"UPDATE dbo.VENDOR_SETUP_REQUEST SET {set_clause} WHERE ID=?"
    try:
        conn = SafeConnection(_env(), "DB_APP_SUPPORT", None, direct=True)
        conn.execute(sql, list(updates.values()) + [req_id])
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API: delete (admin only) ──────────────────────────────────────────────────

@vendor_setup_bp.route("/api/request/<int:req_id>", methods=["DELETE"])
@login_required
def api_delete(req_id):
    user   = session.get("user", {})
    email  = user.get("email", "")
    is_dev = session.get("is_developer", False)
    if not is_dev and not _is_admin(email):
        return jsonify({"error": "Forbidden"}), 403
    try:
        conn = SafeConnection(_env(), "DB_APP_SUPPORT", None, direct=True)
        conn.execute("DELETE FROM dbo.VENDOR_SETUP_REQUEST WHERE ID=?", (req_id,))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API: download document ────────────────────────────────────────────────────

@vendor_setup_bp.route("/api/request/<int:req_id>/doc/<doc_slot>")
@login_required
def api_doc(req_id, doc_slot):
    slot_map = {"w9": ("DOC_W9", "DOC_W9_NAME"), "insurance": ("DOC_INSURANCE", "DOC_INSURANCE_NAME"), "other": ("DOC_OTHER", "DOC_OTHER_NAME")}
    if doc_slot not in slot_map:
        return jsonify({"error": "Invalid doc slot"}), 400
    col_data, col_name = slot_map[doc_slot]
    try:
        conn = SafeConnection(_env(), "DB_APP_SUPPORT", None, direct=True)
        row  = conn.fetchall(f"SELECT {col_data}, {col_name} FROM dbo.VENDOR_SETUP_REQUEST WHERE ID=?", (req_id,))
        if not row or not row[0][0]:
            return jsonify({"error": "Not found"}), 404
        data_bytes, filename = row[0]
        return send_file(io.BytesIO(data_bytes), download_name=filename or "document", as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
