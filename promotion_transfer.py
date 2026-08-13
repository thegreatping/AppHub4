"""Promotion/Transfer Alert module — submit PAF alerts for promotions and transfers.

Data store: SharePoint list 'PAF Alert' on peakcampus.sharepoint.com/sites/BaseCampApps
List GUID : a0e4b87f-4153-4243-a5dc-abeffbc0b002
Auth      : Microsoft Graph API (MSAL client-credentials flow, same as Peak Link)
"""
from flask import Blueprint, render_template, session, jsonify, request
from auth import login_required
from modules import MODULES, APP_ID_MAP
import sys
from helpers import load_env, SafeConnection
from datetime import datetime
from graph_client import get_site_id, list_items, create_item

SP_SITE_PATH = "peakcampus.sharepoint.com:/sites/BaseCampApps"
SP_LIST_ID   = "a0e4b87f-4153-4243-a5dc-abeffbc0b002"

_site_id_cache = {}


def _sp_site():
    """Return the resolved Graph site ID (cached)."""
    if not _site_id_cache:
        _site_id_cache["id"] = get_site_id(SP_SITE_PATH)
    return _site_id_cache["id"]

paf_bp = Blueprint("paf", __name__, url_prefix="/paf")

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
        if m["id"] == 27:
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
        "SELECT COUNT(*) FROM dbo.APP_ADMINS WHERE APP_ID = 27 AND LOWER(ADMIN_EMAIL) = ?",
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
        active_module="promotion_transfer_alert",
        user=session.get("user", {}),
        is_developer=session.get("is_developer", False),
        is_dev_mode=session.get("is_dev_mode", False),
        is_impersonating=session.get("is_impersonating", False),
        impersonating_user=session.get("impersonating_user", None),
        version=APP_VERSION,
    )


@paf_bp.route("/")
@login_required
def index():
    check = _require_access()
    if check:
        return check
    ctx = _get_shell_context()
    ctx["is_admin"] = _is_admin()
    return render_template("promotion_transfer.html", **ctx)


# ── Reference data ──────────────────────────────────────────────────────────────

@paf_bp.route("/api/employees")
@login_required
def api_employees():
    check = _require_access()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    cur = conn.execute("""
        SELECT EMPLOYEE_CODE, NAME_FULL, NAME_FIRST, NAME_LAST,
               TITLE, SUPERVISOR_NAME, SUPERVISOR_EMAIL, EMAIL_AD, LOCATION_AD, TYPE
        FROM xtemp.EMPLOYEE_F
        WHERE STATUS = 'ACTIVE'
        ORDER BY NAME_FULL
    """)
    results = []
    for r in cur.fetchall():
        results.append({
            "code": r[0] or "",
            "name": r[1] or "",
            "first": r[2] or "",
            "last": r[3] or "",
            "title": r[4] or "",
            "supervisor_name": r[5] or "",
            "supervisor_email": r[6] or "",
            "email": r[7] or "",
            "location": r[8] or "",
            "emp_type": r[9] or "",
        })
    return jsonify(results)


@paf_bp.route("/api/properties")
@login_required
def api_properties():
    check = _require_access()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    cur = conn.execute("""
        SELECT PROPERTY_KEY, PROPERTY_NAME, MGMT_ENTITY, PAYROLL_ENTITY
        FROM dbo.PROPERTY_0
        WHERE FLAG_REPORTABLE = 1 AND FLAG_DISPOSITIONED = 0
          AND (FLAG_STUDENT_ONLY = 1 OR FLAG_CONVENTIONAL_ONLY = 1)
        ORDER BY PROPERTY_NAME
    """)
    results = []
    for r in cur.fetchall():
        results.append({
            "key": r[0],
            "name": r[1] or "",
            "entity": r[2] or "",
            "payroll": r[3] or "",
        })
    return jsonify(results)


@paf_bp.route("/api/payroll-entities")
@login_required
def api_payroll_entities():
    check = _require_access()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    cur = conn.execute("""
        SELECT DISTINCT PAYROLL_ENTITY_NAME
        FROM dbo.PAYROLL_ENTITY
        WHERE PAYROLL_ENTITY_NAME <> '--' AND PAYROLL_ENTITY_NAME IS NOT NULL
        ORDER BY PAYROLL_ENTITY_NAME
    """)
    return jsonify([r[0] for r in cur.fetchall()])


# ── Form submission ─────────────────────────────────────────────────────────────

@paf_bp.route("/api/alerts", methods=["POST"])
@login_required
def api_submit():
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    emp_name = data.get("employee_name", "").strip()
    if not emp_name:
        return jsonify({"error": "Employee name is required."}), 400
    if not data.get("paf_type"):
        return jsonify({"error": "PAF Type (Promotion or Transfer) is required."}), 400
    if not data.get("effective_date"):
        return jsonify({"error": "Effective date is required."}), 400
    if not data.get("new_position_title"):
        return jsonify({"error": "New position/title is required."}), 400

    eff_raw = data.get("effective_date", "")
    try:
        effective_date = datetime.strptime(eff_raw, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Invalid effective date format."}), 400

    user = session.get("user", {})
    from config import APP_VERSION

    pos_title = data.get("new_position_title", "").strip()
    custom_title = data.get("custom_position_title", "").strip()

    # Build SharePoint field payload
    sp_fields = {
        "Title":             emp_name,
        "field_0":           emp_name,
        "field_2":           data.get("employee_code", "").strip(),
        "field_5":           effective_date.strftime("%Y-%m-%dT06:00:00Z"),
        "field_6":           data.get("location_type", "").strip(),
        "field_7":           data.get("new_office_location", "").strip(),
        "field_8":           data.get("new_company_entity", "").strip(),
        "field_9":           data.get("new_department", "").strip(),
        "field_10":          data.get("new_property_location", "").strip(),
        "field_11":          data.get("new_home_office_location", "").strip(),
        "field_12":          data.get("new_payroll_entity", "").strip(),
        "field_13":          pos_title if pos_title != "Other" else "",
        "Placeholder1":      custom_title if pos_title == "Other" else "",
        "field_14":          data.get("new_pay_type", "").strip(),
        "field_27":          data.get("special_payment_requests", "").strip(),
        "field_37":          data.get("other_information", "").strip(),
        "CurrentRentDiscount_x003f_":   bool(data.get("rent_discount")),
        "CellPhoneReimbUnchanged_x003f_": not bool(data.get("cell_phone_reimbursement")),
        "RelocationAssistance_x003f_":  bool(data.get("relocation_assistance")),
        "PaycomClient_x003f_":  bool(data.get("paycom_client")),
        "Amex_x003f_":         bool(data.get("amex")),
        "Certify_x003f_":      bool(data.get("certify")),
        "Adaptive_x003f_":     bool(data.get("adaptive_insights")),
        "Avid_x003f_":         bool(data.get("avidxchange")),
        "Concur_x003f_":       bool(data.get("concur")),
        "GraceHill_x003f_":    bool(data.get("grace_hill")),
        "Submittedby":         user.get("email", ""),
        "ProdVersion":         APP_VERSION,
        "JobReq_x003f_":       bool(data.get("job_req")),
        "PAFType":             data.get("paf_type", "").strip(),
        "HiringManagerName":   data.get("hiring_manager_name", "").strip(),
        "HiringManagerEmail":  data.get("hiring_manager_email", "").strip(),
        "RMProperties":        data.get("rm_properties", "").strip(),
    }
    # Only include numeric fields when they have a value
    if data.get("new_hourly_rate"):
        sp_fields["field_15"] = float(data["new_hourly_rate"])
    if data.get("new_annual_salary"):
        sp_fields["field_16"] = float(data["new_annual_salary"])
    if data.get("rent_discount_pct"):
        sp_fields["field_19"] = float(data["rent_discount_pct"])
    if data.get("base_rent"):
        sp_fields["field_21"] = float(data["base_rent"])
    if data.get("cell_phone_amount"):
        sp_fields["field_23"] = float(data["cell_phone_amount"])
    if data.get("relocation_amount"):
        sp_fields["field_26"] = float(data["relocation_amount"])

    try:
        create_item(_sp_site(), SP_LIST_ID, sp_fields)
    except Exception as e:
        return jsonify({"error": f"SharePoint submission failed: {e}"}), 500

    # Also write to EMP_TITLE_OVERRIDES so the new title takes effect in AppHub
    emp_code = data.get("employee_code", "").strip()
    emp_first = data.get("employee_first", "").strip()
    emp_last = data.get("employee_last", "").strip()
    new_title = custom_title if pos_title == "Other" else pos_title
    if emp_code and new_title:
        env = _get_env()
        conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
        date_active = effective_date.strftime("%Y%m%d")
        conn.execute("""
            INSERT INTO dbo.EMP_TITLE_OVERRIDES (DATE_ACTIVE, EMPLOYEE_CODE, NAME_FIRST, NAME_LAST, NEW_TITLE)
            VALUES (?, ?, ?, ?, ?)
        """, [date_active, emp_code, emp_first, emp_last, new_title])

    return jsonify({"success": True, "message": "PAF Alert submitted successfully."})


# ── Admin: view submissions ─────────────────────────────────────────────────────

def _fmt_sp_date(val):
    """Format a SharePoint ISO date string to MM/DD/YYYY, or '' if missing."""
    if not val:
        return ""
    try:
        return datetime.strptime(val[:10], "%Y-%m-%d").strftime("%m/%d/%Y")
    except ValueError:
        return val[:10]


@paf_bp.route("/api/alerts", methods=["GET"])
@login_required
def api_alerts():
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin access required"}), 403
    try:
        rows = list_items(_sp_site(), SP_LIST_ID)
    except Exception as e:
        return jsonify({"error": f"SharePoint read failed: {e}"}), 500

    # Sort descending by SharePoint item ID
    rows.sort(key=lambda x: int(x.get("id", 0)), reverse=True)

    results = []
    for f in rows:
        pos = f.get("field_13") or f.get("Placeholder1") or ""
        results.append({
            "id":              f.get("id", ""),
            "employee_name":   f.get("field_0") or "",
            "employee_code":   f.get("field_2") or "",
            "effective_date":  _fmt_sp_date(f.get("field_5")),
            "paf_type":        f.get("PAFType") or "",
            "location_type":   f.get("field_6") or "",
            "property":        f.get("field_10") or "",
            "department":      f.get("field_9") or "",
            "position":        pos,
            "hiring_manager":  f.get("HiringManagerName") or "",
            "pay_type":        f.get("field_14") or "",
            "hourly_rate":     f.get("field_15"),
            "annual_salary":   f.get("field_16"),
            "rent_discount":   1 if f.get("CurrentRentDiscount_x003f_") else 0,
            "rent_discount_pct": f.get("field_19"),
            "base_rent":       f.get("field_21"),
            "cell_reimb":      0 if f.get("CellPhoneReimbUnchanged_x003f_") else 1,
            "cell_amount":     f.get("field_23"),
            "relocation":      1 if f.get("RelocationAssistance_x003f_") else 0,
            "relocation_amount": f.get("field_26"),
            "company_entity":  f.get("field_8") or "",
            "payroll_entity":  f.get("field_12") or "",
            "paycom":          1 if f.get("PaycomClient_x003f_") else 0,
            "adaptive":        1 if f.get("Adaptive_x003f_") else 0,
            "amex":            1 if f.get("Amex_x003f_") else 0,
            "avidxchange":     1 if f.get("Avid_x003f_") else 0,
            "certify":         1 if f.get("Certify_x003f_") else 0,
            "concur":          1 if f.get("Concur_x003f_") else 0,
            "grace_hill":      1 if f.get("GraceHill_x003f_") else 0,
            "special_payments": f.get("field_27") or "",
            "other_info":      f.get("field_37") or "",
            "submitted_by":    f.get("Submittedby") or "",
            "date_submitted":  _fmt_sp_date(f.get("Modified")),
        })
    return jsonify(results)


# ── Admin management ────────────────────────────────────────────────────────────

@paf_bp.route("/api/admins", methods=["GET"])
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
        "SELECT ID, ADMIN_EMAIL, DATE_CREATED FROM dbo.APP_ADMINS WHERE APP_ID = 27 ORDER BY ID"
    )
    return jsonify([
        {"id": r[0], "email": r[1], "date_created": r[2].strftime("%m/%d/%Y") if r[2] else None}
        for r in cur.fetchall()
    ])


@paf_bp.route("/api/admins", methods=["POST"])
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
        "SELECT COUNT(*) FROM dbo.APP_ADMINS WHERE APP_ID = 27 AND LOWER(ADMIN_EMAIL) = ?",
        [email]
    )
    if cur.fetchone()[0] > 0:
        return jsonify({"error": "Already an admin."}), 400
    conn.execute(
        "INSERT INTO dbo.APP_ADMINS (APP_ID, APP_NAME, ADMIN_EMAIL, DATE_CREATED) VALUES (?, ?, ?, ?)",
        [27, "Promotion/Transfer Alert", email, datetime.now()]
    )
    return jsonify({"success": True})


@paf_bp.route("/api/admins/<int:admin_id>", methods=["DELETE"])
@login_required
def api_remove_admin(admin_id):
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin access required"}), 403
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    conn.execute("DELETE FROM dbo.APP_ADMINS WHERE ID = ? AND APP_ID = 27", [admin_id])
    return jsonify({"success": True})
