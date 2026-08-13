"""New Hire Alert module — submit and manage new hire onboarding alerts."""
from flask import Blueprint, render_template, session, jsonify, request
from auth import login_required
from modules import MODULES, APP_ID_MAP
import sys
from helpers import load_env, SafeConnection
from datetime import datetime

newhire_bp = Blueprint("newhire", __name__, url_prefix="/new-hire")

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
        if m["id"] == 16:
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
        "SELECT COUNT(*) FROM dbo.APP_ADMINS WHERE APP_ID = 16 AND LOWER(ADMIN_EMAIL) = ?",
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
        active_module="new_hire_alert",
        user=session.get("user", {}),
        is_developer=session.get("is_developer", False),
        is_dev_mode=session.get("is_dev_mode", False),
        is_impersonating=session.get("is_impersonating", False),
        impersonating_user=session.get("impersonating_user", None),
        version=APP_VERSION,
    )


@newhire_bp.route("/")
@login_required
def index():
    check = _require_access()
    if check:
        return check
    ctx = _get_shell_context()
    ctx["is_admin"] = _is_admin()
    return render_template("new_hire.html", **ctx)


@newhire_bp.route("/api/alerts", methods=["GET"])
@login_required
def api_alerts():
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin access required"}), 403
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    cur = conn.execute("""
        SELECT ID, Legal_First_Name, Legal_Last_Name, Preferred_First_Name,
               Position_Title, Property_Location, Department, Employee_Start_Date,
               Employee_Status, Pay_Type, Base_Hourly_Rate, Annual_Salary,
               Manager_Name, Submitted_by, Date, Location,
               Entrata, Grace_Hill, Certify, Concur, AMEX, AvidXchange,
               Adaptive_Insights, New_Computer_Order, Paycom_Client_Account,
               Rent_Discount, Rent_Discount_Percentage, Relocation_Assistance,
               Relocation_Assistance_Amount, Cell_Phone_Reimbursement,
               Cell_Phone_Reimbursement_Amount, Other_Information,
               Payroll_Entity_Name, Peak_Entity_Name, Office_Location,
               Special_Payment_Requests, Rehire_Former_Employee, Allocated_Employee,
               Base_Rent, Home_Office_Location, Employee_ID
        FROM dbo.NEW_HIRE_ALERTS
        ORDER BY ID DESC
    """)
    results = []
    for r in cur.fetchall():
        results.append({
            "id": r[0],
            "first_name": r[1] or "",
            "last_name": r[2] or "",
            "preferred_name": r[3] or "",
            "position": r[4] or "",
            "property": r[5] or "",
            "department": r[6] or "",
            "start_date": r[7].strftime("%m/%d/%Y") if r[7] else "",
            "status": r[8] or "",
            "pay_type": r[9] or "",
            "hourly_rate": float(r[10]) if r[10] else None,
            "annual_salary": float(r[11]) if r[11] else None,
            "manager": r[12] or "",
            "submitted_by": r[13] or "",
            "date_submitted": r[14].strftime("%m/%d/%Y") if r[14] else "",
            "location_type": r[15] or "",
            "entrata": r[16] or 0,
            "grace_hill": r[17] or 0,
            "certify": r[18] or 0,
            "concur": r[19] or 0,
            "amex": r[20] or 0,
            "avidxchange": r[21] or 0,
            "adaptive_insights": r[22] or 0,
            "new_computer": r[23] or 0,
            "paycom": r[24] or 0,
            "rent_discount": r[25] or 0,
            "rent_discount_pct": float(r[26]) if r[26] else None,
            "relocation": r[27] or 0,
            "relocation_amount": float(r[28]) if r[28] else None,
            "cell_reimburse": r[29] or 0,
            "cell_amount": float(r[30]) if r[30] else None,
            "other_info": r[31] or "",
            "payroll_entity": r[32] or "",
            "peak_entity": r[33] or "",
            "office_location": r[34] or "",
            "special_payments": r[35] or "",
            "rehire": r[36] or 0,
            "allocated": r[37] or 0,
            "base_rent": float(r[38]) if r[38] else None,
            "home_office": r[39] or "",
            "employee_id": r[40] or "",
        })
    return jsonify(results)


@newhire_bp.route("/api/alerts", methods=["POST"])
@login_required
def api_submit_alert():
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    first = data.get("legal_first_name", "").strip()
    last = data.get("legal_last_name", "").strip()
    if not first or not last:
        return jsonify({"error": "First and last name are required."}), 400

    start_date = None
    if data.get("start_date"):
        try:
            start_date = datetime.strptime(data["start_date"], "%Y-%m-%d")
        except ValueError:
            pass

    user = session.get("user", {})
    from config import APP_VERSION
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    conn.execute("""
        INSERT INTO dbo.NEW_HIRE_ALERTS
            (Legal_First_Name, Legal_Last_Name, Legal_Middle_Name, Preferred_First_Name,
             Employee_ID, Employee_Start_Date, Employee_Status, Department,
             Position_Title, Manager_Name, Location, Property_Location,
             Home_Office_Location, Office_Location, Pay_Type, Base_Hourly_Rate,
             Annual_Salary, Cell_Phone_Reimbursement, Cell_Phone_Reimbursement_Amount,
             Entrata, Grace_Hill, Certify, Concur, AMEX, AvidXchange,
             Adaptive_Insights, Paycom_Client_Account, New_Computer_Order,
             Rent_Discount, Rent_Discount_Percentage, Relocation_Assistance,
             Relocation_Assistance_Amount, Base_Rent, Payroll_Entity_Name,
             Peak_Entity_Name, Rehire_Former_Employee, Allocated_Employee,
             Special_Payment_Requests, Other_Information, Submitted_by, Date,
             PROD_VERSION)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, [
        first,
        last,
        data.get("legal_middle_name", "").strip(),
        data.get("preferred_first_name", "").strip(),
        data.get("employee_id", "").strip(),
        start_date,
        data.get("employee_status", "").strip(),
        data.get("department", "").strip(),
        data.get("position_title", "").strip(),
        data.get("manager_name", "").strip(),
        data.get("location_type", "").strip(),
        data.get("property_location", "").strip(),
        data.get("home_office_location", "").strip(),
        data.get("office_location", "").strip(),
        data.get("pay_type", "").strip(),
        float(data["base_hourly_rate"]) if data.get("base_hourly_rate") else None,
        float(data["annual_salary"]) if data.get("annual_salary") else None,
        1 if data.get("cell_phone_reimbursement") else 0,
        float(data["cell_phone_amount"]) if data.get("cell_phone_amount") else None,
        1 if data.get("entrata") else 0,
        1 if data.get("grace_hill") else 0,
        1 if data.get("certify") else 0,
        1 if data.get("concur") else 0,
        1 if data.get("amex") else 0,
        1 if data.get("avidxchange") else 0,
        1 if data.get("adaptive_insights") else 0,
        1 if data.get("paycom_client_account") else 0,
        1 if data.get("new_computer_order") else 0,
        1 if data.get("rent_discount") else 0,
        float(data["rent_discount_pct"]) if data.get("rent_discount_pct") else None,
        1 if data.get("relocation_assistance") else 0,
        float(data["relocation_amount"]) if data.get("relocation_amount") else None,
        float(data["base_rent"]) if data.get("base_rent") else None,
        data.get("payroll_entity_name", "").strip(),
        data.get("peak_entity_name", "").strip(),
        1 if data.get("rehire") else 0,
        1 if data.get("allocated_employee") else 0,
        data.get("special_payment_requests", "").strip(),
        data.get("other_information", "").strip(),
        user.get("email", "Unknown"),
        datetime.now(),
        APP_VERSION,
    ])
    return jsonify({"success": True, "message": "New hire alert submitted successfully."})


@newhire_bp.route("/api/admins", methods=["GET"])
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
        "SELECT ID, ADMIN_EMAIL, DATE_CREATED FROM dbo.APP_ADMINS WHERE APP_ID = 16 ORDER BY ID"
    )
    results = []
    for r in cur.fetchall():
        results.append({
            "id": r[0],
            "email": r[1],
            "date_created": r[2].strftime("%m/%d/%Y") if r[2] else None,
        })
    return jsonify(results)


@newhire_bp.route("/api/admins", methods=["POST"])
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
        "SELECT COUNT(*) FROM dbo.APP_ADMINS WHERE APP_ID = 16 AND LOWER(ADMIN_EMAIL) = ?",
        [email]
    )
    if cur.fetchone()[0] > 0:
        return jsonify({"error": "Already an admin."}), 400
    conn.execute(
        "INSERT INTO dbo.APP_ADMINS (APP_ID, APP_NAME, ADMIN_EMAIL, DATE_CREATED) VALUES (?, ?, ?, ?)",
        [16, "New Hire Alert", email, datetime.now()]
    )
    return jsonify({"success": True})


@newhire_bp.route("/api/admins/<int:admin_id>", methods=["DELETE"])
@login_required
def api_remove_admin(admin_id):
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin access required"}), 403
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    conn.execute("DELETE FROM dbo.APP_ADMINS WHERE ID = ? AND APP_ID = 16", [admin_id])
    return jsonify({"success": True})


@newhire_bp.route("/api/properties")
@login_required
def api_properties():
    check = _require_access()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        rows = conn.fetchall("""
            SELECT PROPERTY_NAME, PROPERTY_KEY
            FROM dbo.APP_LOCATION_LIST
            WHERE FLAG_REPORTABLE = 1
              AND FLAG_DISPOSITIONED = 0
              AND FLAG_CORPORATE_LOCATION = 0
              AND FLAG_NON_PROPERTY = 0
            ORDER BY PROPERTY_NAME
        """)
        return jsonify([f"{r[0]} - {r[1]}" for r in rows])
    finally:
        conn.close()


@newhire_bp.route("/api/entities")
@login_required
def api_entities():
    check = _require_access()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        payroll_rows = conn.fetchall("""
            SELECT DISTINCT PAYROLL_ENTITY FROM dbo.PROPERTY_0
            WHERE PAYROLL_ENTITY IS NOT NULL
              AND PAYROLL_ENTITY != ''
              AND PAYROLL_ENTITY != '--'
            ORDER BY PAYROLL_ENTITY
        """)
        peak_rows = conn.fetchall("""
            SELECT DISTINCT MGMT_ENTITY FROM dbo.PROPERTY_0
            WHERE MGMT_ENTITY IS NOT NULL
              AND MGMT_ENTITY != ''
              AND MGMT_ENTITY != '--'
            ORDER BY MGMT_ENTITY
        """)
        return jsonify({
            "payroll": [r[0] for r in payroll_rows],
            "peak":    [r[0] for r in peak_rows],
        })
    finally:
        conn.close()
