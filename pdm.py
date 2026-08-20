"""Property Data Manager (PDM) module — manage property master data."""
from flask import Blueprint, render_template, session, jsonify, request
from auth import login_required
from modules import MODULES, APP_ID_MAP
from nav import build_nav_modules
import sys
import datetime
from helpers import load_env, SafeConnection

pdm_bp = Blueprint("pdm", __name__, url_prefix="/pdm")

_env = None


def _get_env():
    global _env
    if _env is None:
        _env = load_env()
    return _env


PDM_ADMINS = {
    "cpell@peakmade.com",
    "agraham@peakmade.com",
    "rmadhu@peakmade.com",
    "rmahaffey@peakmade.com",
}


def _require_access():
    """Check that the current user has access to PDM (app_id=8)."""
    if session.get("is_developer"):
        return None
    user_modules = session.get("user_modules", [])
    for m in user_modules:
        if m["id"] == 8:
            return None
    return jsonify({"error": "unauthorized"}), 403


def _require_admin():
    """Check that the current user is a PDM admin (stub creation, etc.)."""
    if session.get("is_developer"):
        return None
    email = (session.get("user") or {}).get("email", "").lower()
    if email in PDM_ADMINS:
        return None
    return jsonify({"error": "admin access required"}), 403


# ─── PAGE ROUTE ─────────────────────────────────────────────────────────────────

@pdm_bp.route("/")
@login_required
def index():
    """Render the PDM page within the shell framework."""
    check = _require_access()
    if check:
        return check
    from config import APP_VERSION
    visible = build_nav_modules()
    return render_template("pdm.html",
                           modules=visible,
                           active_module="property_data_manager",
                           user=session.get("user", {}),
                           is_developer=session.get("is_developer", False),
                           is_dev_mode=session.get("is_dev_mode", False),
                           is_impersonating=session.get("is_impersonating", False),
                           impersonating_user=session.get("impersonating_user", None),
                           version=APP_VERSION)


# ─── PROPERTY SEARCH ────────────────────────────────────────────────────────────

@pdm_bp.route("/api/properties/search")
@login_required
def search_properties():
    check = _require_access()
    if check:
        return check

    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()          # managed, dispositioned, all
    property_group = request.args.get("property_group", "").strip()
    market = request.args.get("market", "").strip()

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conditions = []
        params = []

        if q:
            conditions.append("""(UPPER(PROPERTY_NAME) LIKE '%' + UPPER(?) + '%'
                OR UPPER(ADDRESS_CITY) LIKE '%' + UPPER(?) + '%'
                OR UPPER(SCHOOL_NAME) LIKE '%' + UPPER(?) + '%'
                OR CAST(PROPERTY_KEY AS VARCHAR) = ?)""")
            params.extend([q, q, q, q])

        if status == "managed":
            conditions.append("FLAG_MANAGED = 1 AND (FLAG_DISPOSITIONED = 0 OR FLAG_DISPOSITIONED IS NULL)")
        elif status == "dispositioned":
            conditions.append("FLAG_DISPOSITIONED = 1")
        elif status == "reportable":
            conditions.append("FLAG_REPORTABLE = 1")
        elif status != "all":
            # Default: managed + not dispositioned
            conditions.append("FLAG_MANAGED = 1 AND (FLAG_DISPOSITIONED = 0 OR FLAG_DISPOSITIONED IS NULL)")

        if property_group:
            conditions.append("UPPER(PROPERTY_GROUP) = UPPER(?)")
            params.append(property_group)

        if market:
            conditions.append("UPPER(MARKET_CITY_STATE) = UPPER(?)")
            params.append(market)

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT TOP 500 * FROM dbo.PROPERTY_0 WHERE {where} ORDER BY PROPERTY_NAME"

        cur = conn.execute(sql, params if params else None)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()

        data = []
        for row in rows:
            d = {}
            for c, v in zip(cols, row):
                if c in ("RowVer",):
                    continue
                if isinstance(v, bytes):
                    continue
                d[c] = v
            data.append(d)

        return jsonify({"properties": data, "count": len(data)})
    finally:
        conn.close()


# ─── FILTER OPTIONS ─────────────────────────────────────────────────────────────

@pdm_bp.route("/api/properties/filter-options")
@login_required
def filter_options():
    check = _require_access()
    if check:
        return check

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        cur = conn.execute("SELECT DISTINCT PROPERTY_GROUP FROM dbo.PROPERTY_0 WHERE PROPERTY_GROUP IS NOT NULL ORDER BY PROPERTY_GROUP")
        groups = [r[0] for r in cur.fetchall()]

        cur = conn.execute("SELECT DISTINCT MARKET_CITY_STATE FROM dbo.PROPERTY_0 WHERE MARKET_CITY_STATE IS NOT NULL ORDER BY MARKET_CITY_STATE")
        markets = [r[0] for r in cur.fetchall()]

        return jsonify({"property_groups": groups, "markets": markets})
    finally:
        conn.close()


# ─── PROPERTY UPDATE (inline edit) ──────────────────────────────────────────────

@pdm_bp.route("/api/properties/<int:property_key>", methods=["PATCH"])
@login_required
def update_property(property_key):
    check = _require_access()
    if check:
        return check

    data = request.get_json()
    if not data:
        return jsonify({"error": "no data"}), 400

    # Whitelist of editable columns
    EDITABLE = {
        'PROPERTY_NAME', 'ADDRESS_1', 'ADDRESS_2', 'ADDRESS_CITY', 'ADDRESS_STATE', 'ADDRESS_ZIP',
        'PHONE_1', 'PHONE_2', 'PHONE_FAX', 'EMAIL',
        'PM_NAME', 'PM_EMAIL', 'PM_EMP_CODE',
        'RM_NAME', 'RM_EMAIL', 'RM_EMP_CODE',
        'RVP_NAME', 'RVP_EMAIL', 'RVP_EMP_CODE',
        'AM_NAME', 'AM_EMAIL', 'AM_EMP_CODE',
        'LM_NAME', 'LM_EMAIL', 'LM_EMP_CODE',
        'MAINT_SUPV_NAME', 'MAINT_SUPV_EMAIL', 'MAINT_SUPV_EMP_CODE',
        'EXEC_DIR_NAME', 'EXEC_DIR_EMAIL', 'EXEC_DIR_EMP_CODE',
        'ACCOUNTANT', 'ACCOUNTANT_EMP_CODE',
        'ACCOUNTING_MGR', 'ACCOUNTING_MGR_EMP_CODE',
        'CONTROLLER', 'CONTROLLER_EMP_CODE',
        'ASSISTANT_CONTROLLER', 'ASSISTANT_CONTROLLER_EMP_CODE',
        'RESIDENT_DIR_NAME', 'RESIDENT_DIR_EMAIL', 'RESIDENT_DIR_EMP_CODE',
        'RAM_NAME', 'RAM_EMP_CODE',
        'RMLS_NAME', 'RMLS_EMAIL', 'RMLS_EMP_CODE',
        'CS_REP_NAME', 'CS_REP_EMAIL', 'CS_REP_EMP_CODE',
        'CS_MGR_NAME', 'CS_MGR_EMAIL', 'CS_MGR_EMP_CODE',
        'PROPERTY_GROUP', 'PROPERTY_GROUP_KEY', 'PROPERTY_TYPE', 'PROPERTY_TYPE_KEY',
        'MARKET_KEY', 'MARKET_CITY', 'MARKET_STATE', 'MARKET_CITY_STATE',
        'OWNER', 'OWNER_GROUP', 'OWNER_SHORT', 'OWNER_GROUP_SHORT',
        'SCHOOL_NAME', 'SCHOOL_ACRONYM', 'SCHOOL_INITIALS', 'SCHOOL_MASCOT',
        'MANAGEMENT_TYPE', 'MANAGEMENT_TYPE_KEY', 'STATUS',
        'FLAG_REPORTABLE', 'FLAG_MANAGED', 'FLAG_DISPOSITIONED', 'FLAG_LEASEUP',
        'FLAG_STABILIZED', 'FLAG_PENDING', 'FLAG_TENTATIVE',
        'APARTMENT_COUNT', 'BED_COUNT_CUSTOM', 'BUILDING_COUNT', 'GROSS_SQFT', 'RENTABLE_SQFT',
        'BUILD_YEAR', 'SAME_STORE_YEAR',
        'NOTES', 'PAYROLL_ENTITY', 'ENTITY_NAME', 'ENTITY_NUMBER',
        'COMPANY', 'LEGAL_ENTITY', 'TAX_ID',
        'URL_WEBSITE', 'URL_FACEBOOK', 'URL_INSTAGRAM', 'URL_TWITTER', 'URL_SHARED_FOLDER',
        'GOOGLE_PROPERTY_LINK', 'GOOGLE_PROPERTY_TYPE',
        'LATITUDE', 'LONGITUDE', 'TIME_ZONE',
        'OFFICE_HOURS_1', 'OFFICE_HOURS_2', 'OFFICE_HOURS_3', 'OFFICE_HOURS_4', 'OFFICE_HOURS_5',
        'BILLING_ALLOCATION_PARTNERS', 'BILLING_ALLOCATION_PCT',
        'APARTMENT_COUNT_BILLING', 'BED_COUNT_BILLING',
    }

    sets = []
    vals = []
    for col, val in data.items():
        if col not in EDITABLE:
            continue
        sets.append(f"[{col}] = ?")
        vals.append(val if val != "" else None)

    if not sets:
        return jsonify({"error": "no valid fields"}), 400

    vals.append(property_key)
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        sql = f"UPDATE dbo.PROPERTY_0 SET {', '.join(sets)} WHERE PROPERTY_KEY = ?"
        conn.execute(sql, vals)
        return jsonify({"ok": True})
    finally:
        conn.close()


# ─── PROPERTY GROUPS ─────────────────────────────────────────────────────────────

@pdm_bp.route("/api/property-groups")
@login_required
def get_property_groups():
    check = _require_access()
    if check:
        return check

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        cur = conn.execute("SELECT * FROM dbo.PROPERTY_GROUP_0 ORDER BY PROPERTY_GROUP_NAME")
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        return jsonify({"groups": rows})
    finally:
        conn.close()


@pdm_bp.route("/api/property-groups", methods=["POST"])
@login_required
def add_property_group():
    check = _require_access()
    if check:
        return check

    data = request.get_json()
    name = (data.get("PROPERTY_GROUP_NAME") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        # Check duplicate
        cur = conn.execute("SELECT COUNT(*) FROM dbo.PROPERTY_GROUP_0 WHERE UPPER(PROPERTY_GROUP_NAME) = UPPER(?)", [name])
        if cur.fetchone()[0] > 0:
            return jsonify({"error": "duplicate"}), 409
        conn.execute("INSERT INTO dbo.PROPERTY_GROUP_0 (PROPERTY_GROUP_NAME, FLAG_ACTIVE) VALUES (?, 1)", [name])
        return jsonify({"ok": True}), 201
    finally:
        conn.close()


@pdm_bp.route("/api/property-groups/<int:key>", methods=["PATCH"])
@login_required
def update_property_group(key):
    check = _require_access()
    if check:
        return check

    data = request.get_json()
    sets, vals = [], []
    if "PROPERTY_GROUP_NAME" in data:
        sets.append("PROPERTY_GROUP_NAME = ?")
        vals.append(data["PROPERTY_GROUP_NAME"])
    if "FLAG_ACTIVE" in data:
        sets.append("FLAG_ACTIVE = ?")
        vals.append(data["FLAG_ACTIVE"])
    if not sets:
        return jsonify({"error": "no fields"}), 400

    vals.append(key)
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute(f"UPDATE dbo.PROPERTY_GROUP_0 SET {', '.join(sets)} WHERE PROPERTY_GROUP_KEY = ?", vals)
        return jsonify({"ok": True})
    finally:
        conn.close()


# ─── MARKETS ─────────────────────────────────────────────────────────────────────

@pdm_bp.route("/api/markets")
@login_required
def get_markets():
    check = _require_access()
    if check:
        return check

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        cur = conn.execute("SELECT * FROM dbo.MARKETS ORDER BY MARKET_CITY_STATE")
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        return jsonify({"markets": rows})
    finally:
        conn.close()


@pdm_bp.route("/api/markets", methods=["POST"])
@login_required
def add_market():
    check = _require_access()
    if check:
        return check

    data = request.get_json()
    city = (data.get("MARKET_CITY") or "").strip()
    state = (data.get("MARKET_STATE") or "").strip()
    if not city or not state:
        return jsonify({"error": "city and state required"}), 400

    city_state = f"{city}, {state}"
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        cur = conn.execute("SELECT COUNT(*) FROM dbo.MARKETS WHERE UPPER(MARKET_CITY_STATE) = UPPER(?)", [city_state])
        if cur.fetchone()[0] > 0:
            return jsonify({"error": "duplicate"}), 409
        conn.execute("INSERT INTO dbo.MARKETS (MARKET_CITY, MARKET_STATE, MARKET_CITY_STATE) VALUES (?, ?, ?)",
                     [city, state, city_state])
        return jsonify({"ok": True}), 201
    finally:
        conn.close()


@pdm_bp.route("/api/markets/<int:key>", methods=["PATCH"])
@login_required
def update_market(key):
    check = _require_access()
    if check:
        return check

    data = request.get_json()
    sets, vals = [], []
    for col in ("MARKET_CITY", "MARKET_STATE", "MARKET_CITY_STATE"):
        if col in data:
            sets.append(f"{col} = ?")
            vals.append(data[col])
    if not sets:
        return jsonify({"error": "no fields"}), 400

    vals.append(key)
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute(f"UPDATE dbo.MARKETS SET {', '.join(sets)} WHERE MARKET_KEY = ?", vals)
        return jsonify({"ok": True})
    finally:
        conn.close()


# ─── EMPLOYEE LOOKUP (for staff dropdowns) ───────────────────────────────────────

@pdm_bp.route("/api/employees")
@login_required
def get_employees():
    """Return active employees for staff assignment dropdowns."""
    check = _require_access()
    if check:
        return check

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        cur = conn.execute("""
            SELECT EMPLOYEE_CODE, NAME_FULL, EMAIL, TITLE, TITLE_GROUP
            FROM dbo.EMPLOYEE_SECURITY_0
            WHERE FLAG_ACTIVE = 1
            ORDER BY NAME_FULL
        """)
        rows = [{"EMPLOYEE_CODE": r[0], "NAME_FULL": r[1], "EMAIL": r[2],
                 "TITLE": r[3], "TITLE_GROUP": r[4]} for r in cur.fetchall()]
        return jsonify({"employees": rows})
    finally:
        conn.close()


# ─── FIELD OVERRIDES ─────────────────────────────────────────────────────────────

@pdm_bp.route("/api/overrides/<int:property_key>")
@login_required
def get_overrides(property_key):
    check = _require_access()
    if check:
        return check

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        cur = conn.execute("SELECT FIELD_NAME FROM dbo.PDM_FIELD_OVERRIDES WHERE PROPERTY_KEY = ?", [property_key])
        fields = [r[0] for r in cur.fetchall()]
        return jsonify({"overrides": fields})
    finally:
        conn.close()


@pdm_bp.route("/api/overrides/<int:property_key>", methods=["POST"])
@login_required
def toggle_override(property_key):
    check = _require_access()
    if check:
        return check

    data = request.get_json()
    field = (data.get("field") or "").strip()
    enabled = data.get("enabled", True)
    if not field:
        return jsonify({"error": "field required"}), 400

    user_email = session.get("user", {}).get("email", "unknown")
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        if enabled:
            cur = conn.execute("SELECT COUNT(*) FROM dbo.PDM_FIELD_OVERRIDES WHERE PROPERTY_KEY = ? AND FIELD_NAME = ?",
                               [property_key, field])
            if cur.fetchone()[0] == 0:
                conn.execute("INSERT INTO dbo.PDM_FIELD_OVERRIDES (PROPERTY_KEY, FIELD_NAME, CREATED_BY) VALUES (?, ?, ?)",
                             [property_key, field, user_email])
        else:
            conn.execute("DELETE FROM dbo.PDM_FIELD_OVERRIDES WHERE PROPERTY_KEY = ? AND FIELD_NAME = ?",
                         [property_key, field])
        return jsonify({"ok": True})
    finally:
        conn.close()


# ─── NEXT PROPERTY KEY (admin only) ────────────────────────────────────────────

@pdm_bp.route("/api/properties/next_key")
@login_required
def next_property_key():
    check = _require_access()
    if check:
        return check
    check = _require_admin()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        cur = conn.execute(
            "SELECT MAX(PROPERTY_KEY) FROM dbo.PROPERTY_0 WHERE PROPERTY_KEY < 5000"
        )
        max_key = cur.fetchone()[0] or 0
        return jsonify({"next_key": max_key + 1})
    finally:
        conn.close()


# ─── CREATE STUB PROPERTY (admin only) ──────────────────────────────────────────

@pdm_bp.route("/api/properties/create", methods=["POST"])
@login_required
def create_property():
    check = _require_access()
    if check:
        return check
    check = _require_admin()
    if check:
        return check

    data = request.get_json()
    if not data:
        return jsonify({"error": "no data"}), 400

    # Required field
    prop_name = (data.get("PROPERTY_NAME") or "").strip().upper()
    if not prop_name:
        return jsonify({"error": "PROPERTY_NAME is required"}), 400

    today_int = int(datetime.date.today().strftime("%Y%m%d"))
    created_by = (session.get("user") or {}).get("email", "unknown")

    # Next Sunday as DATE_KEY for COMP_FACT (matching Power Apps logic)
    today = datetime.date.today()
    days_until_sunday = (6 - today.weekday()) % 7
    next_sunday = today + datetime.timedelta(days=days_until_sunday if days_until_sunday else 7)
    next_sunday_int = int(next_sunday.strftime("%Y%m%d"))

    # Academic year: AY is the year the fall semester starts (Aug-Jul cycle)
    this_ay = today.year if today.month >= 8 else today.year - 1

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        # ── 1. Compute next PROPERTY_KEY (internal: key < 5000) ──────────────
        cur = conn.execute(
            "SELECT MAX(PROPERTY_KEY) FROM dbo.PROPERTY_0 WHERE PROPERTY_KEY < 5000"
        )
        max_key = cur.fetchone()[0] or 0
        new_key = max_key + 1

        # ── 2. Insert into PROPERTY_0 ─────────────────────────────────────────
        prop_fields = {
            "PROPERTY_KEY":     new_key,
            "PROPERTY_NAME":    prop_name,
            "ADDRESS_1":        data.get("ADDRESS_1") or None,
            "ADDRESS_2":        data.get("ADDRESS_2") or None,
            "ADDRESS_CITY":     data.get("ADDRESS_CITY") or None,
            "ADDRESS_STATE":    data.get("ADDRESS_STATE") or None,
            "ADDRESS_ZIP":      data.get("ADDRESS_ZIP") or None,
            "ADDRESS_COUNTRY":  data.get("ADDRESS_COUNTRY") or "US",
            "APARTMENT_COUNT":  data.get("APARTMENT_COUNT") or None,
            "BED_COUNT_STATIC": data.get("BED_COUNT_STATIC") or None,
            "BUILD_YEAR":       data.get("BUILD_YEAR") or None,
            "BUILDING_COUNT":   data.get("BUILDING_COUNT") or None,
            "COMPANY":          data.get("COMPANY") or None,
            "EMAIL":            data.get("EMAIL") or None,
            "ENTITY_NUMBER":    data.get("ENTITY_NUMBER") or None,
            "LEGAL_ENTITY":     data.get("LEGAL_ENTITY") or None,
            "OWNER":            data.get("OWNER") or None,
            "PHONE_1":          data.get("PHONE_1") or None,
            "DATE_CREATED":     today_int,
            "DATE_ADDED_TO_DW": today_int,
            "SOURCE_SYSTEM":    data.get("SOURCE_SYSTEM") or "INTERNAL",
            "FLAG_ACTIVE":      0,
            "FLAG_MANAGED":     0,
            "FLAG_REPORTABLE":  0,
            "FLAG_PENDING":     1,
            "FLAG_DISPOSITIONED": 0,
            "FLAG_STUDENT_ONLY": 0,
            "FLAG_CONVENTIONAL_ONLY": 0,
            "FLAG_NON_PROPERTY": 0,
        }
        cols = list(prop_fields.keys())
        vals = list(prop_fields.values())
        placeholders = ", ".join(["?"] * len(cols))
        col_list = ", ".join(cols)
        conn.execute(
            f"INSERT INTO dbo.PROPERTY_0 ({col_list}) VALUES ({placeholders})",
            vals
        )

        # ── 3. Insert into PARENT_PROPERTY ────────────────────────────────────
        pp_fields = {
            "PROPERTY_KEY":  new_key,
            "PROPERTY_NAME": prop_name,
            "ADDRESS_1":     data.get("ADDRESS_1") or None,
            "ADDRESS_CITY":  data.get("ADDRESS_CITY") or None,
            "ADDRESS_STATE": data.get("ADDRESS_STATE") or None,
            "ADDRESS_ZIP":   data.get("ADDRESS_ZIP") or None,
        }
        # Only insert columns that exist in PARENT_PROPERTY — use same pattern
        pp_cols = list(pp_fields.keys())
        pp_vals = list(pp_fields.values())
        pp_ph = ", ".join(["?"] * len(pp_cols))
        conn.execute(
            f"INSERT INTO dbo.PARENT_PROPERTY ({', '.join(pp_cols)}) VALUES ({pp_ph})",
            pp_vals
        )

        # ── 4. Insert into COMP_PROPERTY ──────────────────────────────────────
        cp_fields = {
            "PROPERTY_KEY":  new_key,
            "PROPERTY_NAME": prop_name,
            "ADDRESS_1":     data.get("ADDRESS_1") or None,
            "ADDRESS_CITY":  data.get("ADDRESS_CITY") or None,
            "ADDRESS_STATE": data.get("ADDRESS_STATE") or None,
            "ADDRESS_ZIP":   data.get("ADDRESS_ZIP") or None,
            "FLAG_ACTIVE":   0,
            "FLAG_COMP":     0,
            "FLAG_PARENT":   0,
            "FLAG_REPORTABLE": 0,
            "FLAG_DISPOSITIONED": 0,
            "FLAG_STUDENT_ONLY": 0,
            "FLAG_CONVENTIONAL_ONLY": 0,
            "FLAG_MIXED_USE": 0,
            "FLAG_EXCLUDE_FROM_CALCS": 0,
            "FLAG_INCLUDE_COMP": 0,
            "FLAG_COMPLETE_LOGIC": 0,
            "FLAG_AMENITY_BASKETBALL": 0,
            "FLAG_AMENITY_BUSINESS_CTR": 0,
            "FLAG_AMENITY_COFFEE_BAR": 0,
            "FLAG_AMENITY_COURTYARDS": 0,
            "FLAG_AMENITY_FIRE_PITS": 0,
            "FLAG_AMENITY_FITNESS_CTR": 0,
            "FLAG_AMENITY_GAME_ROOM": 0,
            "FLAG_AMENITY_GOLF_SIMULATOR": 0,
            "FLAG_AMENITY_HAMMOCKS": 0,
            "FLAG_AMENITY_HOT_TUB": 0,
            "FLAG_AMENITY_ON_BUS_ROUTE": 0,
            "FLAG_AMENITY_ON_SITE_RETAIL": 0,
            "FLAG_AMENITY_OUTDOOR_GRILLING": 0,
            "FLAG_AMENITY_PACKAGE_LOCKERS": 0,
            "FLAG_AMENITY_POOL": 0,
            "FLAG_AMENITY_STUDY_ROOMS": 0,
            "FLAG_AMENITY_SHUTTLE": 0,
            "FLAG_AMENITY_TANNING": 0,
            "FLAG_AMENITY_TENNIS": 0,
            "FLAG_AMENITY_THEATER": 0,
            "FLAG_AMENITY_VOLLEYBALL": 0,
            "FLAG_OTHER5": 0,
        }
        cp_cols = list(cp_fields.keys())
        cp_vals = list(cp_fields.values())
        cp_ph = ", ".join(["?"] * len(cp_cols))
        conn.execute(
            f"INSERT INTO dbo.COMP_PROPERTY ({', '.join(cp_cols)}) VALUES ({cp_ph})",
            cp_vals
        )

        # ── 5. Insert into COMP_ASSIGNMENTS ───────────────────────────────────
        parent_comp_key = str(new_key) + "." + str(new_key)
        conn.execute(
            """INSERT INTO dbo.COMP_ASSIGNMENTS
               (PARENT_COMP_KEY, DATE_KEY, COMP_PROPERTY_KEY, COMP_PROPERTY_NAME,
                PARENT_PROPERTY_KEY, PARENT_PROPERTY_NAME, FLAG_COMP, FLAG_PARENT)
               VALUES (?, ?, ?, ?, ?, ?, 0, 0)""",
            [parent_comp_key, today_int, new_key, prop_name, new_key, prop_name]
        )

        # ── 6. Insert into COMP_FACT ──────────────────────────────────────────
        conn.execute(
            """INSERT INTO dbo.COMP_FACT
               (DATE_KEY, DATE_UPDATED, AY, UPDATED_BY, PROPERTY_KEY, PROPERTY_NAME)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [next_sunday_int, today_int, this_ay, created_by, new_key, prop_name]
        )

        return jsonify({"ok": True, "PROPERTY_KEY": new_key, "PROPERTY_NAME": prop_name})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


# ─── ADMIN CHECK ─────────────────────────────────────────────────────────────────

@pdm_bp.route("/api/is_admin")
@login_required
def check_is_admin():
    check = _require_access()
    if check:
        return check
    email = (session.get("user") or {}).get("email", "").lower()
    is_admin = session.get("is_developer") or (email in PDM_ADMINS)
    return jsonify({"is_admin": bool(is_admin)})
