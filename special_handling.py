"""Special Handling Form module.

Submit special handling payment requests for vendor invoices that require
routing outside the standard AvidXchange cycle.

Data store : SharePoint list on peakcampus.sharepoint.com/sites/BaseCampApps
List GUID  : 2da8a0b9-7dd1-47ed-b5e6-eb7c4ccd9227
APP ID     : 18

Attachments per submission:
  1. Invoice                       (required)
  2. RM Approval                   (required)
  3. Spreadsheet of account        (optional)
     numbers and amounts to be paid
"""
from flask import Blueprint, render_template, session, jsonify, request
from auth import login_required
from modules import MODULES, APP_ID_MAP
from nav import build_nav_modules
from helpers import load_env, SafeConnection
from rush_check import GL_CODES, SHIPPING_METHODS, US_STATES
from datetime import datetime

special_handling_bp = Blueprint("special_handling", __name__, url_prefix="/special-handling")

APP_ID   = 18
APP_NAME = "Special Handling Form"
SP_SITE_PATH = "peakcampus.sharepoint.com:/sites/BaseCampApps"
SP_SITE_BASE  = "https://peakcampus.sharepoint.com/sites/BaseCampApps"
SP_LIST_ID   = "2da8a0b9-7dd1-47ed-b5e6-eb7c4ccd9227"

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
        if m["id"] == APP_ID:
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
        "SELECT COUNT(*) FROM dbo.APP_ADMINS WHERE APP_ID = ? AND LOWER(ADMIN_EMAIL) = ?",
        [APP_ID, email],
    )
    return cur.fetchone()[0] > 0


def _get_shell_context():
    from config import APP_VERSION
    visible = build_nav_modules()
    return dict(
        modules=visible,
        active_module="special_handling_form",
        user=session.get("user", {}),
        is_developer=session.get("is_developer", False),
        is_dev_mode=session.get("is_dev_mode", False),
        is_impersonating=session.get("is_impersonating", False),
        impersonating_user=session.get("impersonating_user", None),
        version=APP_VERSION,
    )


def _sp():
    from graph_client import get_site_id
    return get_site_id(SP_SITE_PATH), SP_LIST_ID


# ─── PAGE ROUTE ──────────────────────────────────────────────────────────────────

@special_handling_bp.route("/")
@login_required
def index():
    check = _require_access()
    if check:
        return check
    ctx = _get_shell_context()
    ctx["is_admin"] = _is_admin()
    ctx["shipping_methods"] = SHIPPING_METHODS
    ctx["us_states"] = US_STATES
    ctx["gl_codes"] = GL_CODES
    return render_template("special_handling.html", **ctx)


# ─── API: PROPERTIES ─────────────────────────────────────────────────────────────

@special_handling_bp.route("/api/properties", methods=["GET"])
@login_required
def api_properties():
    check = _require_access()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    cur = conn.execute("""
        SELECT PROPERTY_NAME, RM_NAME, RM_EMAIL, RVP_NAME, RVP_EMAIL,
               ACCOUNTANT, ENTITY_NUMBER
        FROM dbo.PROPERTY_0
        WHERE FLAG_REPORTABLE = 1
          AND FLAG_DISPOSITIONED = 0
          AND ADDRESS_COUNTRY = 'US'
        ORDER BY PROPERTY_NAME
    """)
    rows = cur.fetchall()
    return jsonify([{
        "name":          r[0],
        "rm_name":       r[1] or "",
        "rm_email":      r[2] or "",
        "rvp_name":      r[3] or "",
        "rvp_email":     r[4] or "",
        "accountant":    r[5] or "",
        "entity_number": r[6] or "",
    } for r in rows])


# ─── API: GL CODES ────────────────────────────────────────────────────────────────

@special_handling_bp.route("/api/gl-codes", methods=["GET"])
@login_required
def api_gl_codes():
    check = _require_access()
    if check:
        return check
    return jsonify(GL_CODES)


# ─── API: VENDORS ─────────────────────────────────────────────────────────────────

@special_handling_bp.route("/api/vendors", methods=["GET"])
@login_required
def api_vendors():
    check = _require_access()
    if check:
        return check
    q = (request.args.get("q") or "").strip()
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    if q:
        cur = conn.execute("""
            SELECT TOP 30 VENDOR_KEY, VENDOR_NAME, ADDRESS, CITY, STATE, ZIP
            FROM dbo.VENDOR
            WHERE FLAG_ACTIVE = 1
              AND VENDOR_NAME LIKE ?
            ORDER BY VENDOR_NAME
        """, [f"%{q}%"])
    else:
        cur = conn.execute("""
            SELECT TOP 100 VENDOR_KEY, VENDOR_NAME, ADDRESS, CITY, STATE, ZIP
            FROM dbo.VENDOR
            WHERE FLAG_ACTIVE = 1
            ORDER BY VENDOR_NAME
        """)
    rows = cur.fetchall()
    return jsonify([{
        "vendor_key":  r[0],
        "vendor_name": r[1] or "",
        "address":     r[2] or "",
        "city":        r[3] or "",
        "state":       r[4] or "",
        "zip":         r[5] or "",
    } for r in rows])


# ─── API: SUBMISSION TYPES ────────────────────────────────────────────────────────

@special_handling_bp.route("/api/submission-types", methods=["GET"])
@login_required
def api_submission_types():
    check = _require_access()
    if check:
        return check
    try:
        from graph_client import get_site_id, get_list_columns
        site_id = get_site_id(SP_SITE_PATH)
        cols = get_list_columns(site_id, SP_LIST_ID)
        for col in cols:
            if col.get("name") == "SubmissionType":
                choices = col.get("choice", {}).get("choices", [])
                if choices:
                    return jsonify(choices)
        return jsonify([])
    except Exception:
        return jsonify([])


# ─── API: SUBMIT ─────────────────────────────────────────────────────────────────

@special_handling_bp.route("/api/submit", methods=["POST"])
@login_required
def api_submit():
    check = _require_access()
    if check:
        return check

    f = request.form

    property_name        = (f.get("property") or "").strip()
    rm_name              = (f.get("rm_name") or "").strip()
    rm_email             = (f.get("rm_email") or "").strip()
    rvp_name             = (f.get("rvp_name") or "").strip()
    rvp_email            = (f.get("rvp_email") or "").strip()
    accountant           = (f.get("accountant") or "").strip()
    submission_type      = (f.get("submission_type") or "").strip()
    vendor_name          = (f.get("vendor_name") or "").strip()
    vendor_id            = (f.get("vendor_id") or "").strip()
    street_address       = (f.get("street_address") or "").strip()
    vendor_city          = (f.get("vendor_city") or "").strip()
    vendor_state         = (f.get("vendor_state") or "").strip()
    vendor_zip           = (f.get("vendor_zip") or "").strip()
    invoice_number       = (f.get("invoice_number") or "").strip()
    date_needed          = (f.get("date_needed") or "").strip()
    shipping_method      = (f.get("shipping_method") or "").strip()
    special_instructions = (f.get("special_instructions") or "").strip()
    check_amount_raw     = (f.get("check_amount") or "0").strip()
    authorization        = (f.get("authorization") or "").strip()

    line_items = []
    for i in range(1, 5):
        line_items.append({
            "entity_id":   (f.get(f"entity_id{i}") or "").strip(),
            "gl_code":     (f.get(f"gl_code{i}") or "").strip(),
            "description": (f.get(f"description{i}") or "").strip(),
            "amount":      (f.get(f"amount{i}") or "0").strip(),
        })

    # ── Server-side validation ──────────────────────────────────────────────────
    required = {
        "Property":              property_name,
        "Submission Type":       submission_type,
        "Vendor Name":           vendor_name,
        "Vendor Street Address": street_address,
        "Vendor City":           vendor_city,
        "Vendor State":          vendor_state,
        "Vendor Zip":            vendor_zip,
        "Invoice Number":        invoice_number,
        "Date Needed":           date_needed,
        "Shipping Method":       shipping_method,
        "Check Amount":          check_amount_raw,
    }
    for label, val in required.items():
        if not val:
            return jsonify({"error": f"{label} is required."}), 400

    if not authorization:
        return jsonify({"error": "Authorization acknowledgment is required."}), 400

    if shipping_method not in SHIPPING_METHODS:
        return jsonify({"error": "Invalid shipping method."}), 400

    try:
        check_amount = round(float(check_amount_raw), 2)
    except ValueError:
        return jsonify({"error": "Check Amount must be a number."}), 400

    try:
        amounts = [round(float(li["amount"]), 2) for li in line_items]
    except ValueError:
        return jsonify({"error": "All Amount fields must be numeric."}), 400

    total = round(sum(amounts), 2)
    if total == 0:
        return jsonify({"error": "At least one line item with an amount is required."}), 400

    for i, li in enumerate(line_items, 1):
        if amounts[i - 1] > 0:
            if not li["entity_id"]:
                return jsonify({"error": f"Entity ID {i} is required when Amount {i} is entered."}), 400
            if not li["gl_code"]:
                return jsonify({"error": f"GL Code {i} is required when Amount {i} is entered."}), 400
            if not li["description"]:
                return jsonify({"error": f"Description {i} is required when Amount {i} is entered."}), 400

    if round(check_amount, 2) != round(total, 2):
        return jsonify({"error": f"Check Amount (${check_amount:,.2f}) must equal the sum of line item amounts (${total:,.2f})."}), 400

    # Invoice and RM Approval are required; spreadsheet is optional
    invoice_file    = request.files.get("attach_invoice")
    rm_approval_file = request.files.get("attach_rm_approval")
    spreadsheet_file = request.files.get("attach_spreadsheet")

    if not invoice_file or not invoice_file.filename:
        return jsonify({"error": "Invoice attachment is required."}), 400
    if not rm_approval_file or not rm_approval_file.filename:
        return jsonify({"error": "RM Approval attachment is required."}), 400

    try:
        dt = datetime.strptime(date_needed, "%Y-%m-%d")
        date_needed_iso = dt.strftime("%Y-%m-%dT00:00:00Z")
    except ValueError:
        return jsonify({"error": "Invalid Date Needed format."}), 400

    user = session.get("user", {})
    submitter_name  = user.get("name", "")
    submitter_email = user.get("email", "")

    sp_fields = {
        "Submittedby":                   submitter_name,
        "SubmittedEmail":                submitter_email,
        "Property":                      property_name,
        "RM":                            rm_name,
        "RVP":                           rvp_name,
        "PropertyAccountant":            accountant,
        "RMEmail":                       rm_email,
        "RVPEmail":                      rvp_email,
        "SubmissionType":                {"Value": submission_type},
        "Vendor":                        vendor_name,
        "VendorID":                      vendor_id,
        "StreetAddress":                 street_address,
        "VendorCity":                    vendor_city,
        "VendorState_x002f_Province":    vendor_state,
        "VendorZip_x002f_PostalCode":    vendor_zip,
        "InvoiceNumber":                 invoice_number,
        "DateNeeded":                    date_needed_iso,
        "ShippingMethod":                {"Value": shipping_method},
        "CheckAmounr":                   check_amount,   # SP field has a typo — kept as-is
        "Total":                         total,
        "EntityID1":                     line_items[0]["entity_id"],
        "GLCode1":                       line_items[0]["gl_code"],
        "Description1":                  line_items[0]["description"],
        "Amount1":                       amounts[0],
        "Authorization":                 authorization,
    }

    if special_instructions:
        sp_fields["SpecialInstructions"] = special_instructions

    for i in range(1, 4):
        if amounts[i] > 0:
            sp_fields[f"EntityID{i+1}"]    = line_items[i]["entity_id"]
            sp_fields[f"GLCode{i+1}"]      = line_items[i]["gl_code"]
            sp_fields[f"Description{i+1}"] = line_items[i]["description"]
            sp_fields[f"Amount{i+1}"]      = amounts[i]

    # ── Create SP list item ─────────────────────────────────────────────────────
    try:
        from graph_client import create_item, add_sp_attachment
        site_id, list_id = _sp()
        created = create_item(site_id, list_id, sp_fields)
        item_id = created.get("_item_id", "")
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    except Exception as exc:
        return jsonify({"error": f"SharePoint error creating item: {exc}"}), 500

    # ── Upload attachments ──────────────────────────────────────────────────────
    attach_errors = []
    uploads = [
        ("Invoice",       invoice_file,      "invoice"),
        ("RM Approval",   rm_approval_file,  "rm_approval"),
    ]
    if spreadsheet_file and spreadsheet_file.filename:
        uploads.append(("Spreadsheet", spreadsheet_file, "spreadsheet"))

    for label, file_obj, safe_prefix in uploads:
        try:
            import os
            ext = os.path.splitext(file_obj.filename)[1]
            add_sp_attachment(SP_SITE_BASE, SP_LIST_ID, item_id, f"{safe_prefix}{ext}", file_obj.read())
        except Exception as exc:
            attach_errors.append(f"{label}: {exc}")

    if attach_errors:
        return jsonify({
            "success": True,
            "warning": "Request submitted but some attachments failed to upload: " + "; ".join(attach_errors),
        })

    return jsonify({"success": True, "message": "Special Handling Request submitted successfully."})


# ─── API: SUBMISSIONS (admin) ─────────────────────────────────────────────────────

@special_handling_bp.route("/api/submissions", methods=["GET"])
@login_required
def api_submissions():
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
        shipping = row.get("ShippingMethod") or {}
        sub_type = row.get("SubmissionType") or {}
        results.append({
            "id":               row.get("_item_id", ""),
            "submitted_by":     row.get("Submittedby", ""),
            "submitted_email":  row.get("SubmittedEmail", ""),
            "property":         row.get("Property", ""),
            "vendor":           row.get("Vendor", ""),
            "invoice_number":   row.get("InvoiceNumber", ""),
            "date_needed":      row.get("DateNeeded", ""),
            "submission_type":  sub_type.get("Value", "") if isinstance(sub_type, dict) else str(sub_type or ""),
            "shipping_method":  shipping.get("Value", "") if isinstance(shipping, dict) else str(shipping or ""),
            "check_amount":     row.get("CheckAmounr", 0),
            "total":            row.get("Total", 0),
            "status":           row.get("Status", ""),
            "tracking_comments": row.get("TrackingNumber_x002f_Comments", ""),
            "processed_by":     row.get("ProcessedBy", ""),
            "rm":               row.get("RM", ""),
            "rvp":              row.get("RVP", ""),
            "created":          row.get("Created", ""),
        })

    results.sort(key=lambda x: x["created"], reverse=True)
    return jsonify(results)


# ─── API: UPDATE SUBMISSION (admin) ───────────────────────────────────────────────

@special_handling_bp.route("/api/submissions/<item_id>", methods=["PATCH"])
@login_required
def api_update_submission(item_id):
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin access required"}), 403

    data = request.get_json()
    patch = {}
    if "status" in data:
        patch["Status"] = data["status"]
    if "tracking_comments" in data:
        patch["TrackingNumber_x002f_Comments"] = data["tracking_comments"]
    if "processed_by" in data:
        patch["ProcessedBy"] = data["processed_by"]

    if not patch:
        return jsonify({"error": "No fields to update"}), 400

    user = session.get("user", {})
    patch["Updatedby"]   = user.get("name", "")
    patch["UpdatedEmail"] = user.get("email", "")
    patch["Updateddat"]  = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        from graph_client import get_site_id
        import requests as _req
        from graph_client import _headers
        site_id = get_site_id(SP_SITE_PATH)
        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{SP_LIST_ID}/items/{item_id}/fields"
        r = _req.patch(url, headers=_headers(), json=patch, timeout=15)
        r.raise_for_status()
    except Exception as exc:
        return jsonify({"error": f"SharePoint error: {exc}"}), 500

    return jsonify({"success": True})


# ─── API: IS ADMIN ────────────────────────────────────────────────────────────────

@special_handling_bp.route("/api/is_admin", methods=["GET"])
@login_required
def api_is_admin():
    check = _require_access()
    if check:
        return check
    return jsonify({"is_admin": _is_admin()})


# ─── API: ADMINS ──────────────────────────────────────────────────────────────────

@special_handling_bp.route("/api/admins", methods=["GET"])
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
        "SELECT ID, ADMIN_EMAIL, DATE_CREATED FROM dbo.APP_ADMINS WHERE APP_ID = ? ORDER BY ID",
        [APP_ID],
    )
    return jsonify([{"id": r[0], "email": r[1], "created": str(r[2])} for r in cur.fetchall()])


@special_handling_bp.route("/api/admins", methods=["POST"])
@login_required
def api_add_admin():
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin access required"}), 403
    data = request.get_json()
    email = (data.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"error": "Valid email required"}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    conn.execute(
        "INSERT INTO dbo.APP_ADMINS (APP_ID, APP_NAME, ADMIN_EMAIL, DATE_CREATED) VALUES (?,?,?,GETDATE())",
        [APP_ID, APP_NAME, email],
    )
    return jsonify({"success": True})


@special_handling_bp.route("/api/admins/<int:admin_id>", methods=["DELETE"])
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
    return jsonify({"success": True})
