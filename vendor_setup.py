"""Vendor Setup Form module.

Browse and manage the vendor master list. Admins can add and edit vendors.

Data source : DB_APP_SUPPORT.dbo.VENDOR
APP_ID      : 17
"""
from flask import Blueprint, render_template, session, jsonify, request
from auth import login_required
from nav import build_nav_modules
from helpers import load_env, SafeConnection
from datetime import datetime, date
import decimal

vendor_setup_bp = Blueprint("vendor_setup", __name__, url_prefix="/vendor-setup")

APP_ID   = 17
APP_NAME = "Vendor Setup Form"

BILLING_FREQS   = ["Monthly", "Annual", "Quarterly", "Per Move-In", "Per Project"]
FLAG_ACTIVE_MAP = {1: "Active", 0: "Inactive", 2: "On Hold"}


def _env():
    return load_env()


def _is_admin(email: str) -> bool:
    try:
        conn = SafeConnection(_env(), "DB_APP_SUPPORT", None, direct=True)
        return bool(conn.fetchall(
            "SELECT 1 FROM dbo.APP_ADMINS WHERE APP_ID=? AND LOWER(ADMIN_EMAIL)=?",
            (APP_ID, email.lower())
        ))
    except Exception:
        return False


def _row_to_dict(r, cols):
    def _v(val):
        if isinstance(val, (datetime, date)):
            return val.strftime("%Y-%m-%d")
        if isinstance(val, decimal.Decimal):
            return float(val)
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
        billing_freqs=BILLING_FREQS,
    )
    ctx.update(kwargs)
    return ctx


# -- Main page -----------------------------------------------------------------

@vendor_setup_bp.route("/")
@login_required
def index():
    conn = SafeConnection(_env(), "DB_APP_SUPPORT", None, direct=True)
    cats = conn.fetchall("SELECT VENDOR_CATEGORY_KEY, VENDOR_CATEGORY FROM dbo.VENDOR_CATEGORY ORDER BY VENDOR_CATEGORY")
    return render_template("vendor_setup.html", **_ctx(categories=cats))


# -- API: list vendors ---------------------------------------------------------

@vendor_setup_bp.route("/api/vendors")
@login_required
def api_list():
    status = request.args.get("status", "").strip()
    cat    = request.args.get("cat", "").strip()
    q      = request.args.get("q", "").strip()

    where, params = ["1=1"], []
    if status != "":
        try: where.append("FLAG_ACTIVE=?"); params.append(int(status))
        except ValueError: pass
    if cat:
        where.append("VENDOR_CATEGORY_KEY=?"); params.append(int(cat))
    if q:
        where.append("(VENDOR_NAME LIKE ? OR REP_NAME LIKE ? OR REP_EMAIL LIKE ?)")
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]

    sql = f"""
        SELECT VENDOR_KEY, VENDOR_NAME, VENDOR_CATEGORY, VENDOR_CATEGORY_KEY,
               FLAG_ACTIVE, FLAG_MSA_VENDOR, FLAG_ENTRATA_FEED_ENABLED,
               BILLING_FREQUENCY, REP_NAME, REP_EMAIL,
               SUPPORT_CONTACT, SUPPORT_CONTACT_EMAIL,
               ADDRESS, CITY, STATE, ZIP, URL,
               GL_KEY, GL_NAME_NUMBER, EXTRA_FEES,
               DATE_CREATED, DATE_MODIFIED, MODIFIED_BY
        FROM dbo.VENDOR
        WHERE {' AND '.join(where)}
        ORDER BY VENDOR_NAME
    """
    try:
        conn = SafeConnection(_env(), "DB_APP_SUPPORT", None, direct=True)
        cur  = conn.execute(sql, params if params else None)
        cols = [d[0] for d in cur.description]
        return jsonify([_row_to_dict(r, cols) for r in cur.fetchall()])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -- API: get single vendor ----------------------------------------------------

@vendor_setup_bp.route("/api/vendor/<int:key>")
@login_required
def api_get(key):
    sql = """
        SELECT VENDOR_KEY, VENDOR_NAME, VENDOR_CATEGORY, VENDOR_CATEGORY_KEY,
               FLAG_ACTIVE, FLAG_MSA_VENDOR, FLAG_ENTRATA_FEED_ENABLED,
               BILLING_FREQUENCY, EXTRA_FEES, TERMS,
               REP_NAME, REP_EMAIL, SUPPORT_CONTACT, SUPPORT_CONTACT_EMAIL,
               ADDRESS, CITY, STATE, ZIP, URL,
               CONTRACT_FOLDER, SERVICES,
               GL_KEY, GL_NAME_NUMBER,
               DATE_CREATED, DATE_MODIFIED, MODIFIED_BY
        FROM dbo.VENDOR WHERE VENDOR_KEY=?
    """
    try:
        conn = SafeConnection(_env(), "DB_APP_SUPPORT", None, direct=True)
        cur  = conn.execute(sql, (key,))
        cols = [d[0] for d in cur.description]
        row  = cur.fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404
        return jsonify(_row_to_dict(row, cols))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -- API: add new vendor (admin) -----------------------------------------------

@vendor_setup_bp.route("/api/vendor", methods=["POST"])
@login_required
def api_add():
    user   = session.get("user", {})
    email  = user.get("email", "")
    is_dev = session.get("is_developer", False)
    if not is_dev and not _is_admin(email):
        return jsonify({"error": "Admin access required."}), 403

    name = (request.form.get("vendor_name") or "").strip()
    if not name:
        return jsonify({"error": "Vendor name is required."}), 400

    def _f(k):
        v = (request.form.get(k) or "").strip()
        return v if v else None

    cat_key  = _f("vendor_category_key")
    cat_name = None
    if cat_key:
        conn     = SafeConnection(_env(), "DB_APP_SUPPORT", None, direct=True)
        row      = conn.fetchall("SELECT VENDOR_CATEGORY FROM dbo.VENDOR_CATEGORY WHERE VENDOR_CATEGORY_KEY=?", (int(cat_key),))
        cat_name = row[0][0] if row else None

    today  = datetime.now().strftime("%Y%m%d")
    fields = {
        "VENDOR_NAME":               name,
        "VENDOR_CATEGORY":           cat_name,
        "VENDOR_CATEGORY_KEY":       int(cat_key) if cat_key else None,
        "FLAG_ACTIVE":               int(_f("flag_active") or 1),
        "FLAG_MSA_VENDOR":           int(_f("flag_msa_vendor") or 0),
        "FLAG_ENTRATA_FEED_ENABLED": int(_f("flag_entrata_feed_enabled") or 0),
        "BILLING_FREQUENCY":         _f("billing_frequency"),
        "EXTRA_FEES":                _f("extra_fees"),
        "TERMS":                     _f("terms"),
        "REP_NAME":                  _f("rep_name"),
        "REP_EMAIL":                 _f("rep_email"),
        "SUPPORT_CONTACT":           _f("support_contact"),
        "SUPPORT_CONTACT_EMAIL":     _f("support_contact_email"),
        "ADDRESS":                   _f("address"),
        "CITY":                      _f("city"),
        "STATE":                     _f("state"),
        "ZIP":                       _f("zip"),
        "URL":                       _f("url"),
        "CONTRACT_FOLDER":           _f("contract_folder"),
        "SERVICES":                  _f("services"),
        "GL_KEY":                    int(_f("gl_key")) if _f("gl_key") else None,
        "GL_NAME_NUMBER":            _f("gl_name_number"),
        "DATE_CREATED":              today,
        "DATE_MODIFIED":             today,
        "MODIFIED_BY":               user.get("name", email),
    }
    fields = {k: v for k, v in fields.items() if v is not None}
    cols   = list(fields.keys())
    sql    = f"INSERT INTO dbo.VENDOR ({', '.join(cols)}) OUTPUT INSERTED.VENDOR_KEY VALUES ({', '.join(['?']*len(cols))})"
    try:
        conn    = SafeConnection(_env(), "DB_APP_SUPPORT", None, direct=True)
        cur     = conn.execute(sql, list(fields.values()))
        new_key = cur.fetchone()[0]
        return jsonify({"VENDOR_KEY": new_key}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -- API: edit vendor (admin) --------------------------------------------------

@vendor_setup_bp.route("/api/vendor/<int:key>", methods=["PATCH"])
@login_required
def api_update(key):
    user   = session.get("user", {})
    email  = user.get("email", "")
    is_dev = session.get("is_developer", False)
    if not is_dev and not _is_admin(email):
        return jsonify({"error": "Admin access required."}), 403

    data    = request.get_json(force=True) or {}
    allowed = {
        "VENDOR_NAME", "VENDOR_CATEGORY", "VENDOR_CATEGORY_KEY",
        "FLAG_ACTIVE", "FLAG_MSA_VENDOR", "FLAG_ENTRATA_FEED_ENABLED",
        "BILLING_FREQUENCY", "EXTRA_FEES", "TERMS",
        "REP_NAME", "REP_EMAIL", "SUPPORT_CONTACT", "SUPPORT_CONTACT_EMAIL",
        "ADDRESS", "CITY", "STATE", "ZIP", "URL",
        "CONTRACT_FOLDER", "SERVICES", "GL_KEY", "GL_NAME_NUMBER",
    }
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": "Nothing to update."}), 400

    updates["DATE_MODIFIED"] = datetime.now().strftime("%Y%m%d")
    updates["MODIFIED_BY"]   = user.get("name", email)

    set_clause = ", ".join(f"{k}=?" for k in updates)
    try:
        conn = SafeConnection(_env(), "DB_APP_SUPPORT", None, direct=True)
        conn.execute(f"UPDATE dbo.VENDOR SET {set_clause} WHERE VENDOR_KEY=?", list(updates.values()) + [key])
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
