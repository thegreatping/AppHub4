"""SAM Contract Manager module.

View, filter, and manage SAM vendor contracts by property.

Data source : DB_APP_SUPPORT.dbo.VENDOR_CONTRACT
APP_ID      : 11

Contract levels: Diamond, Diamond Plus, Gold, Gold Plus, Platinum, Silver, Off
Billing freq  : MONTHLY, ANNUALLY
FLAG_ACTIVE   : 0=Inactive, 1=Active, 2=On Hold
"""
from flask import Blueprint, render_template, session, jsonify, request
from auth import login_required
from modules import MODULES, APP_ID_MAP
from nav import build_nav_modules
from helpers import load_env, SafeConnection
from datetime import datetime, date
import decimal

sam_contract_manager_bp = Blueprint("sam_contract_manager", __name__, url_prefix="/sam-contracts")

APP_ID   = 11
APP_NAME = "SAM Contract Manager"

CONTRACT_LEVELS = ["Diamond Plus", "Diamond", "Platinum", "Gold Plus", "Gold", "Silver", "Off"]
BILLING_FREQS   = ["MONTHLY", "ANNUALLY"]
STATUS_MAP      = {0: "Inactive", 1: "Active", 2: "On Hold"}


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


def _row_to_dict(r):
    """Convert a VENDOR_CONTRACT row tuple to a JSON-safe dict."""
    def _v(val):
        if isinstance(val, (datetime, date)):
            return val.strftime("%Y-%m-%d")
        if isinstance(val, decimal.Decimal):
            return float(val)
        return val
    keys = [
        "CONTRACT_KEY","CONTRACT_AMOUNT","CONTRACT_BILLING_FREQUENCY","CONTRACT_LEVEL",
        "CONTRACT_FOLDER","CONTRACT_NAME","CONTRACT_TERMS","DATE_BEGIN","DATEID_BEGIN",
        "DATETIME_BEGIN","DATE_CREATED","DATE_END","DATEID_END","DATETIME_END",
        "DATE_MODIFIED","FLAG_ACTIVE","FLAG_ALERT_STATUS","LISTING_URL","MODIFIED_BY",
        "NOTES","PROPERTY_KEY","PROPERTY_NAME","VENDOR_KEY","VENDOR_NAME",
    ]
    return {k: _v(v) for k, v in zip(keys, r)}


def _get_template_context(**kwargs):
    user       = session.get("user", {})
    email      = user.get("email", "")
    is_dev     = session.get("is_developer", False)
    is_admin   = is_dev or _is_admin(email)
    visible    = build_nav_modules()
    ctx = dict(
        modules=visible,
        active_module="sam_contract_manager",
        user=user,
        is_developer=is_dev,
        is_admin=is_admin,
        app_name=APP_NAME,
    )
    ctx.update(kwargs)
    return ctx


# ── Main page ─────────────────────────────────────────────────────────────────

@sam_contract_manager_bp.route("/")
@login_required
def index():
    conn = SafeConnection(_get_env(), "DB_APP_SUPPORT", None, direct=True)
    vendors = [r[0] for r in conn.fetchall(
        "SELECT DISTINCT VENDOR_NAME FROM dbo.VENDOR_CONTRACT WHERE VENDOR_NAME IS NOT NULL ORDER BY 1"
    )]
    ctx = _get_template_context(vendors=vendors, levels=CONTRACT_LEVELS)
    return render_template("sam_contract_manager.html", **ctx)


# ── API: list contracts ───────────────────────────────────────────────────────

@sam_contract_manager_bp.route("/api/contracts")
@login_required
def api_list():
    vendor   = request.args.get("vendor", "").strip()
    status   = request.args.get("status", "").strip()   # "0","1","2", or ""
    level    = request.args.get("level", "").strip()
    prop     = request.args.get("prop", "").strip()

    where, params = ["1=1"], []
    if vendor:
        where.append("VENDOR_NAME = ?"); params.append(vendor)
    if status != "":
        try: where.append("FLAG_ACTIVE = ?"); params.append(int(status))
        except ValueError: pass
    if level:
        where.append("CONTRACT_LEVEL = ?"); params.append(level)
    if prop:
        where.append("PROPERTY_NAME LIKE ?"); params.append(f"%{prop}%")

    sql = f"""
        SELECT CONTRACT_KEY, VENDOR_NAME, PROPERTY_NAME, CONTRACT_NAME,
               CONTRACT_LEVEL, CONTRACT_AMOUNT, CONTRACT_BILLING_FREQUENCY,
               DATETIME_BEGIN, DATETIME_END, FLAG_ACTIVE, FLAG_ALERT_STATUS,
               CONTRACT_FOLDER, LISTING_URL
        FROM dbo.VENDOR_CONTRACT
        WHERE {' AND '.join(where)}
        ORDER BY VENDOR_NAME, PROPERTY_NAME
    """
    conn = SafeConnection(_get_env(), "DB_APP_SUPPORT", None, direct=True)
    rows = conn.fetchall(sql, params)

    def _fmt(r):
        def _v(val):
            if isinstance(val, (datetime, date)): return val.strftime("%Y-%m-%d")
            if isinstance(val, decimal.Decimal): return float(val)
            return val
        keys = ["CONTRACT_KEY","VENDOR_NAME","PROPERTY_NAME","CONTRACT_NAME",
                "CONTRACT_LEVEL","CONTRACT_AMOUNT","CONTRACT_BILLING_FREQUENCY",
                "DATETIME_BEGIN","DATETIME_END","FLAG_ACTIVE","FLAG_ALERT_STATUS",
                "CONTRACT_FOLDER","LISTING_URL"]
        return {k: _v(v) for k, v in zip(keys, r)}

    return jsonify([_fmt(r) for r in rows])


# ── API: single contract detail ───────────────────────────────────────────────

@sam_contract_manager_bp.route("/api/contract/<int:key>")
@login_required
def api_get(key):
    conn = SafeConnection(_get_env(), "DB_APP_SUPPORT", None, direct=True)
    rows = conn.fetchall("SELECT * FROM dbo.VENDOR_CONTRACT WHERE CONTRACT_KEY=?", (key,))
    if not rows:
        return jsonify({"error": "not found"}), 404
    return jsonify(_row_to_dict(rows[0]))


# ── API: save (create or update) ──────────────────────────────────────────────

@sam_contract_manager_bp.route("/api/contract", methods=["POST"])
@sam_contract_manager_bp.route("/api/contract/<int:key>", methods=["PATCH"])
@login_required
def api_save(key=None):
    user  = session.get("user", {})
    email = user.get("email", "")
    is_admin = session.get("is_developer", False) or _is_admin(email)
    if not is_admin:
        return jsonify({"error": "unauthorized"}), 403

    data = request.get_json() or {}

    def _clean(val, maxlen=None):
        if val is None: return None
        s = str(val).strip()
        return s[:maxlen] if maxlen and s else (s or None)

    def _date(val):
        if not val: return None
        try: return datetime.strptime(str(val)[:10], "%Y-%m-%d")
        except ValueError: return None

    def _dec(val):
        if val is None or str(val).strip() == "": return None
        try: return decimal.Decimal(str(val))
        except Exception: return None

    def _int(val):
        if val is None: return None
        try: return int(val)
        except Exception: return None

    fields = dict(
        CONTRACT_NAME              = _clean(data.get("CONTRACT_NAME"), 255),
        CONTRACT_AMOUNT            = _dec(data.get("CONTRACT_AMOUNT")),
        CONTRACT_BILLING_FREQUENCY = _clean(data.get("CONTRACT_BILLING_FREQUENCY"), 255),
        CONTRACT_LEVEL             = _clean(data.get("CONTRACT_LEVEL"), 255),
        CONTRACT_FOLDER            = _clean(data.get("CONTRACT_FOLDER"), 255),
        CONTRACT_TERMS             = _clean(data.get("CONTRACT_TERMS"), 2048),
        DATETIME_BEGIN             = _date(data.get("DATETIME_BEGIN")),
        DATETIME_END               = _date(data.get("DATETIME_END")),
        FLAG_ACTIVE                = _int(data.get("FLAG_ACTIVE")) if data.get("FLAG_ACTIVE") is not None else 1,
        FLAG_ALERT_STATUS          = _int(data.get("FLAG_ALERT_STATUS")),
        LISTING_URL                = _clean(data.get("LISTING_URL"), 255),
        NOTES                      = _clean(data.get("NOTES"), 2048),
        PROPERTY_KEY               = _int(data.get("PROPERTY_KEY")),
        PROPERTY_NAME              = _clean(data.get("PROPERTY_NAME"), 255),
        VENDOR_KEY                 = _int(data.get("VENDOR_KEY")),
        VENDOR_NAME                = _clean(data.get("VENDOR_NAME"), 255),
        MODIFIED_BY                = email,
        DATE_MODIFIED              = int(datetime.now().strftime("%Y%m%d")),
    )

    conn = SafeConnection(_get_env(), "DB_APP_SUPPORT", None, direct=True)

    if key is None:
        # INSERT
        cols   = list(fields.keys())
        placeholders = ",".join(["?"] * len(cols))
        col_list     = ",".join(cols)
        conn.execute(
            f"INSERT INTO dbo.VENDOR_CONTRACT ({col_list}) VALUES ({placeholders})",
            list(fields.values())
        )
        new_key = conn.fetchall("SELECT MAX(CONTRACT_KEY) FROM dbo.VENDOR_CONTRACT")[0][0]
        return jsonify({"ok": True, "CONTRACT_KEY": new_key})
    else:
        # UPDATE
        set_clause = ",".join([f"{c}=?" for c in fields.keys()])
        conn.execute(
            f"UPDATE dbo.VENDOR_CONTRACT SET {set_clause} WHERE CONTRACT_KEY=?",
            list(fields.values()) + [key]
        )
        return jsonify({"ok": True, "CONTRACT_KEY": key})


# ── API: delete ───────────────────────────────────────────────────────────────

@sam_contract_manager_bp.route("/api/contract/<int:key>", methods=["DELETE"])
@login_required
def api_delete(key):
    user  = session.get("user", {})
    email = user.get("email", "")
    is_admin = session.get("is_developer", False) or _is_admin(email)
    if not is_admin:
        return jsonify({"error": "unauthorized"}), 403

    conn = SafeConnection(_get_env(), "DB_APP_SUPPORT", None, direct=True)
    conn.execute("DELETE FROM dbo.VENDOR_CONTRACT WHERE CONTRACT_KEY=?", (key,))
    return jsonify({"ok": True})
