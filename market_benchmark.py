"""Market Benchmark module blueprint — /mrb/ prefix."""
import sys
import re
from flask import Blueprint, render_template, jsonify, request, session
from helpers import load_env, SafeConnection
from auth import login_required
from modules import MODULES, APP_ID_MAP
from datetime import date, timedelta

mrb_bp = Blueprint("mrb", __name__, url_prefix="/mrb")

_env = None


def _get_env():
    global _env
    if _env is None:
        _env = load_env()
    return _env


def get_db():
    return SafeConnection(_get_env(), "DB_APP_SUPPORT", None, direct=True)


def _require_access():
    """Check that current user has access to Market Benchmark (app_id=15)."""
    if session.get("is_developer"):
        return None
    for m in session.get("user_modules", []):
        if m["id"] == 15:
            return None
    return jsonify({"error": "unauthorized"}), 403


def _get_modified_by():
    user_info = session.get("user") or {}
    return user_info.get("name", "MRB-App") if isinstance(user_info, dict) else "MRB-App"


def _build_shell_context():
    """Build the template context needed by shell.html."""
    from config import APP_VERSION
    user_modules = session.get("user_modules", [])
    allowed_string_ids = set()
    for m in user_modules:
        string_id = APP_ID_MAP.get(m["id"])
        if string_id:
            allowed_string_ids.add(string_id)
    _always_visible = {"rent_forecasting_2"}
    visible = [m for m in MODULES if m["id"] in allowed_string_ids or m["id"] in _always_visible] if user_modules else MODULES
    return {
        "modules": visible,
        "active_module": "market_benchmark",
        "user": session.get("user", {}),
        "is_developer": session.get("is_developer", False),
        "is_dev_mode": session.get("is_dev_mode", False),
        "is_impersonating": session.get("is_impersonating", False),
        "impersonating_user": session.get("impersonating_user", None),
        "version": APP_VERSION,
    }


# ── Page Route ─────────────────────────────────────────────────────────────────

@mrb_bp.route("/")
@login_required
def index():
    check = _require_access()
    if check:
        return check
    return render_template("market_benchmark.html", **_build_shell_context())


# ── API: Parent Properties ──────────────────────────────────────────────────────

@mrb_bp.route("/api/parent-properties")
@login_required
def api_parent_properties():
    check = _require_access()
    if check:
        return check
    conn = get_db()
    rows = conn.execute("""
        SELECT PROPERTY_KEY, PROPERTY_NAME, MARKET_KEY
        FROM dbo.PROPERTY_0
        WHERE FLAG_REPORTABLE = 1 AND FLAG_DISPOSITIONED = 0
        ORDER BY PROPERTY_NAME
    """).fetchall()
    return jsonify([{"key": r[0], "name": r[1], "market_key": r[2]} for r in rows])


# ── API: Weeks ──────────────────────────────────────────────────────────────────

@mrb_bp.route("/api/weeks")
@login_required
def api_weeks():
    check = _require_access()
    if check:
        return check
    ay = request.args.get("ay", type=int, default=2026)
    conn = get_db()
    today = date.today()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    next_monday = today + timedelta(days=days_until_monday)
    next_monday_int = int(next_monday.strftime('%Y%m%d'))
    rows = conn.execute("""
        SELECT DISTINCT DATE_KEY, AY, RELATIVE_WEEK
        FROM dbo.WEEKS
        WHERE AY = ? AND DATE_KEY < ?
        ORDER BY DATE_KEY DESC
    """, [ay, next_monday_int]).fetchall()
    return jsonify([{"date_key": r[0], "ay": r[1], "relative_week": r[2]} for r in rows])


# ── API: Markets ────────────────────────────────────────────────────────────────

@mrb_bp.route("/api/markets")
@login_required
def api_markets():
    check = _require_access()
    if check:
        return check
    conn = get_db()
    rows = conn.execute("""
        SELECT MARKET_KEY, MARKET_CITY_STATE
        FROM dbo.MARKETS
        WHERE MARKET_CITY_STATE IS NOT NULL AND MARKET_CITY_STATE != ''
        ORDER BY MARKET_CITY_STATE
    """).fetchall()
    return jsonify([{"key": r[0], "name": r[1]} for r in rows])


@mrb_bp.route("/api/markets/all")
@login_required
def api_markets_all():
    check = _require_access()
    if check:
        return check
    q = request.args.get("q", "").strip()
    conn = get_db()
    if q:
        rows = conn.execute("""
            SELECT MARKET_KEY, MARKET_CITY, MARKET_STATE, MARKET_CITY_STATE
            FROM dbo.MARKETS
            WHERE MARKET_CITY_STATE LIKE ? OR MARKET_CITY LIKE ?
            ORDER BY MARKET_CITY_STATE
        """, [f"%{q}%", f"%{q}%"]).fetchall()
    else:
        rows = conn.execute("""
            SELECT MARKET_KEY, MARKET_CITY, MARKET_STATE, MARKET_CITY_STATE
            FROM dbo.MARKETS
            ORDER BY MARKET_CITY_STATE
        """).fetchall()
    return jsonify([{"MARKET_KEY": r[0], "MARKET_CITY": r[1], "MARKET_STATE": r[2], "MARKET_CITY_STATE": r[3]} for r in rows])


@mrb_bp.route("/api/markets/update", methods=["POST"])
@login_required
def api_markets_update():
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    market_key = data.get("market_key")
    field = data.get("field")
    value = data.get("value")
    if market_key is None or not field:
        return jsonify({"error": "missing params"}), 400
    allowed = {"MARKET_CITY", "MARKET_STATE", "MARKET_CITY_STATE"}
    if field not in allowed:
        return jsonify({"error": f"field not allowed: {field}"}), 400
    conn = get_db()
    conn.execute(f"UPDATE dbo.MARKETS SET {field} = ? WHERE MARKET_KEY = ?", [value, market_key])
    conn.commit()
    return jsonify({"ok": True})


@mrb_bp.route("/api/markets/create", methods=["POST"])
@login_required
def api_markets_create():
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    city = (data.get("city") or "").strip()
    state = (data.get("state") or "").strip().upper()
    if not city or not state:
        return jsonify({"error": "city and state required"}), 400
    city_state = f"{city.upper()}, {state}"
    conn = get_db()
    cur = conn.execute("SELECT ISNULL(MAX(MARKET_KEY), 0) + 1 FROM dbo.MARKETS")
    next_key = cur.fetchone()[0]
    conn.execute("""
        INSERT INTO dbo.MARKETS (MARKET_KEY, MARKET_CITY, MARKET_STATE, MARKET_CITY_STATE)
        VALUES (?, ?, ?, ?)
    """, [next_key, city.upper(), state, city_state])
    conn.commit()
    return jsonify({"ok": True, "market_key": next_key})


@mrb_bp.route("/api/markets/delete", methods=["POST"])
@login_required
def api_markets_delete():
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    market_key = data.get("market_key")
    if market_key is None:
        return jsonify({"error": "missing market_key"}), 400
    conn = get_db()
    conn.execute("DELETE FROM dbo.MARKETS WHERE MARKET_KEY = ?", [market_key])
    conn.commit()
    return jsonify({"ok": True})


# ── API: Comp Properties ────────────────────────────────────────────────────────

@mrb_bp.route("/api/comp-properties")
@login_required
def api_comp_properties():
    check = _require_access()
    if check:
        return check
    q = request.args.get("q", "").strip()
    show_inactive = request.args.get("inactive", "0") == "1"
    conn = get_db()
    where = "WHERE cp.PROPERTY_NAME LIKE ?" if q else ("WHERE cp.FLAG_ACTIVE = 1" if not show_inactive else "WHERE 1=1")
    params = [f"%{q}%"] if q else []
    cur = conn.execute(f"""
        SELECT cp.PROPERTY_KEY, cp.PROPERTY_NAME, cp.ADDRESS_1, cp.ADDRESS_CITY, cp.ADDRESS_STATE,
               cp.ADDRESS_ZIP, cp.COMPANY, cp.OWNER, cp.MARKET_KEY, cp.MARKET_CITY_STATE,
               cp.BED_COUNT_STATIC, cp.APARTMENT_COUNT, cp.BUILD_YEAR, cp.DISTANCE_TO_CAMPUS,
               cp.ASSET_CLASS, cp.FLAG_ACTIVE, cp.FLAG_COMP, cp.FLAG_PARENT, cp.URL_WEBSITE,
               CASE WHEN p.PROPERTY_KEY IS NOT NULL THEN 1 ELSE 0 END AS FLAG_IN_PROPERTY0
        FROM dbo.COMP_PROPERTY cp
        LEFT JOIN dbo.PROPERTY_0 p ON p.PROPERTY_KEY = cp.PROPERTY_KEY
        {where}
        ORDER BY cp.PROPERTY_NAME
    """, params)
    cols = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    return jsonify([dict(zip(cols, row)) for row in rows])


@mrb_bp.route("/api/comp-properties/update", methods=["POST"])
@login_required
def api_comp_properties_update():
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    pk = data.get("property_key")
    field = data.get("field")
    value = data.get("value")
    if pk is None or not field:
        return jsonify({"error": "missing params"}), 400
    blocked = {"PROPERTY_KEY", "DATE_CREATED"}
    if field in blocked or not re.match(r'^[A-Z_0-9]+$', field):
        return jsonify({"error": f"field not allowed: {field}"}), 400
    conn = get_db()
    conn.execute(f"UPDATE dbo.COMP_PROPERTY SET {field} = ? WHERE PROPERTY_KEY = ?", [value, pk])
    conn.commit()
    return jsonify({"ok": True})


@mrb_bp.route("/api/comp-properties/detail")
@login_required
def api_comp_properties_detail():
    check = _require_access()
    if check:
        return check
    pk = request.args.get("property_key", type=int)
    if pk is None:
        return jsonify({}), 400
    conn = get_db()
    cur = conn.execute("SELECT * FROM dbo.COMP_PROPERTY WHERE PROPERTY_KEY = ?", [pk])
    cols = [desc[0] for desc in cur.description]
    row = cur.fetchone()
    if not row:
        return jsonify({}), 404
    return jsonify(dict(zip(cols, row)))


@mrb_bp.route("/api/comp-properties/create", methods=["POST"])
@login_required
def api_comp_properties_create():
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    name = (data.get("property_name") or "").strip()
    if not name:
        return jsonify({"error": "property_name required"}), 400
    conn = get_db()
    cur = conn.execute("SELECT ISNULL(MAX(PROPERTY_KEY), 0) + 1 FROM dbo.COMP_PROPERTY")
    next_key = cur.fetchone()[0]
    conn.execute("""
        INSERT INTO dbo.COMP_PROPERTY (PROPERTY_KEY, PROPERTY_NAME, FLAG_ACTIVE, FLAG_COMP)
        VALUES (?, ?, 1, 1)
    """, [next_key, name])
    conn.commit()
    return jsonify({"ok": True, "property_key": next_key})


# ── API: Comp Assignments ──────────────────────────────────────────────────────

@mrb_bp.route("/api/comp-assignments")
@login_required
def api_comp_assignments():
    check = _require_access()
    if check:
        return check
    parent_key = request.args.get("parent_key", type=int)
    date_key = request.args.get("date_key", type=int)
    if not parent_key or not date_key:
        return jsonify([])
    conn = get_db()
    rows = conn.execute("""
        SELECT COMP_PROPERTY_KEY, COMP_PROPERTY_NAME, RANK_ORDER, MARKET_STATE
        FROM dbo.COMP_ASSIGNMENTS
        WHERE PARENT_PROPERTY_KEY = ? AND DATE_KEY = ?
        ORDER BY RANK_ORDER
    """, [parent_key, date_key]).fetchall()
    return jsonify([
        {"comp_property_key": r[0], "comp_property_name": r[1], "rank_order": r[2], "market_state": r[3]}
        for r in rows
    ])


# ── API: Comp Fact ─────────────────────────────────────────────────────────────

@mrb_bp.route("/api/comp-fact")
@login_required
def api_comp_fact():
    check = _require_access()
    if check:
        return check
    property_key = request.args.get("property_key", type=int)
    date_key = request.args.get("date_key", type=int)
    if not property_key or not date_key:
        return jsonify([])
    conn = get_db()
    cur = conn.execute("""
        SELECT * FROM dbo.COMP_FACT
        WHERE PROPERTY_KEY = ? AND DATE_KEY = ?
    """, [property_key, date_key])
    cols = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    return jsonify([dict(zip(cols, row)) for row in rows])


# ── API: Floorplan Fact ────────────────────────────────────────────────────────

@mrb_bp.route("/api/floorplan-fact")
@login_required
def api_floorplan_fact():
    check = _require_access()
    if check:
        return check
    property_key = request.args.get("property_key", type=int)
    date_key = request.args.get("date_key", type=int)
    if not property_key or not date_key:
        return jsonify([])
    conn = get_db()
    cur = conn.execute("""
        SELECT * FROM dbo.FLOORPLAN_FACT
        WHERE PROPERTY_KEY = ? AND DATE_KEY = ? AND FLAG_ACTIVE = 1
        ORDER BY FLOORPLAN_NAME
    """, [property_key, date_key])
    cols = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    return jsonify([dict(zip(cols, row)) for row in rows])


@mrb_bp.route("/api/floorplan-fact/update", methods=["POST"])
@login_required
def api_floorplan_fact_update():
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    key = data.get("floorplan_assignment_key")
    date_key = data.get("date_key")
    field = data.get("field")
    value = data.get("value")
    if not key or not date_key or not field:
        return jsonify({"error": "missing params"}), 400
    allowed = {
        "RENT_PRELEASE_FURNISHED", "CONCESSION_ANNUAL_AMOUNT",
        "GIFT_INCENTIVE_ANNUAL_AMOUNT", "RENT_CURRENT_TERM_FURNISHED",
        "FLAG_SOLD_OUT", "FLAG_NO_PRICING_ONLINE",
        "SUMMARY_PRELEASE_SPECIALS", "SUMMARY_CONCESSIONS",
        "SUMMARY_GIFT_INCENTIVES", "SUMMARY_CURRENT_TERM_SPECIALS",
    }
    if field not in allowed:
        return jsonify({"error": f"field not allowed: {field}"}), 400
    conn = get_db()
    conn.execute(f"""
        UPDATE dbo.FLOORPLAN_FACT
        SET {field} = ?
        WHERE FLOORPLAN_ASSIGNMENT_KEY = ? AND DATE_KEY = ?
    """, [value, key, date_key])
    conn.commit()
    return jsonify({"ok": True})


# ── API: Comp Fact Update ──────────────────────────────────────────────────────

@mrb_bp.route("/api/comp-fact/update", methods=["POST"])
@login_required
def api_comp_fact_update():
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    property_key = data.get("property_key")
    date_key = data.get("date_key")
    field = data.get("field")
    value = data.get("value")
    if not property_key or not date_key or not field:
        return jsonify({"error": "missing params"}), 400
    allowed = {
        "PREMIUM_01_WAIVED", "PREMIUM_02_WAIVED", "PREMIUM_03_WAIVED",
        "PREMIUM_04_WAIVED", "PREMIUM_05_WAIVED",
        "PREMIUM_01", "PREMIUM_02", "PREMIUM_03", "PREMIUM_04", "PREMIUM_05",
        "FEE_01_WAIVED", "FEE_02_WAIVED", "FEE_03_WAIVED", "FEE_04_WAIVED",
        "FEE_05_WAIVED", "FEE_06_WAIVED", "FEE_07_WAIVED", "FEE_08_WAIVED",
        "FEE_09_WAIVED", "FEE_10_WAIVED", "FEE_11_WAIVED", "FEE_12_WAIVED",
        "DEPOSIT_WAIVED",
        "FEE_01", "FEE_02", "FEE_03", "FEE_04", "FEE_05", "FEE_06",
        "FEE_07", "FEE_08", "FEE_09", "FEE_10", "FEE_11", "FEE_12",
    }
    if field not in allowed:
        return jsonify({"error": f"field not allowed: {field}"}), 400
    conn = get_db()
    conn.execute(f"""
        UPDATE dbo.COMP_FACT
        SET {field} = ?
        WHERE PROPERTY_KEY = ? AND DATE_KEY = ?
    """, [value, property_key, date_key])
    conn.commit()
    return jsonify({"ok": True})


# ── API: Schools ────────────────────────────────────────────────────────────────

@mrb_bp.route("/api/schools")
@login_required
def api_schools():
    check = _require_access()
    if check:
        return check
    q = request.args.get("q", "").strip()
    conn = get_db()
    if q:
        cur = conn.execute("""
            SELECT SCHOOL_KEY, SCHOOL_NAME, SCHOOL_TYPE, MARKET_CITY_STATE,
                   SCHOOL_ADDRESS1, SCHOOL_CITY, SCHOOL_STATE, SCHOOL_ZIP,
                   SCHOOL_PHONE1, SCHOOL_CONTACT_PERSON, SCHOOL_SUMMARY,
                   STUDENTS_ENROLLED, STUDENTS_UNDERGRADUATE, STUDENTS_GRADUATE,
                   STUDENTS_ONLINE, STUDENTS_ONSITE, STUDENTS_INTERNATIONAL,
                   BEDS_ON_CAMPUS, BEDS_ON_CAMPUS_OCCUPIED, BEDS_ON_CAMPUS_OCC_PCT,
                   FLAG_ACTIVE, MARKET_KEY
            FROM dbo.SCHOOLS
            WHERE SCHOOL_NAME LIKE ?
            ORDER BY SCHOOL_NAME
        """, [f"%{q}%"])
    else:
        cur = conn.execute("""
            SELECT SCHOOL_KEY, SCHOOL_NAME, SCHOOL_TYPE, MARKET_CITY_STATE,
                   SCHOOL_ADDRESS1, SCHOOL_CITY, SCHOOL_STATE, SCHOOL_ZIP,
                   SCHOOL_PHONE1, SCHOOL_CONTACT_PERSON, SCHOOL_SUMMARY,
                   STUDENTS_ENROLLED, STUDENTS_UNDERGRADUATE, STUDENTS_GRADUATE,
                   STUDENTS_ONLINE, STUDENTS_ONSITE, STUDENTS_INTERNATIONAL,
                   BEDS_ON_CAMPUS, BEDS_ON_CAMPUS_OCCUPIED, BEDS_ON_CAMPUS_OCC_PCT,
                   FLAG_ACTIVE, MARKET_KEY
            FROM dbo.SCHOOLS
            ORDER BY SCHOOL_NAME
        """)
    cols = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    return jsonify([dict(zip(cols, row)) for row in rows])


@mrb_bp.route("/api/schools/update", methods=["POST"])
@login_required
def api_schools_update():
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    school_key = data.get("school_key")
    field = data.get("field")
    value = data.get("value")
    if school_key is None or not field:
        return jsonify({"error": "missing params"}), 400
    allowed = {
        "SCHOOL_NAME", "SCHOOL_TYPE", "SCHOOL_ADDRESS1", "SCHOOL_CITY",
        "SCHOOL_STATE", "SCHOOL_ZIP", "SCHOOL_PHONE1", "SCHOOL_CONTACT_PERSON",
        "SCHOOL_SUMMARY", "MARKET_CITY_STATE", "MARKET_KEY",
        "STUDENTS_ENROLLED", "STUDENTS_UNDERGRADUATE", "STUDENTS_GRADUATE",
        "STUDENTS_ONLINE", "STUDENTS_ONSITE", "STUDENTS_INTERNATIONAL",
        "BEDS_ON_CAMPUS", "BEDS_ON_CAMPUS_OCCUPIED", "BEDS_ON_CAMPUS_OCC_PCT",
        "FLAG_ACTIVE",
    }
    if field not in allowed:
        return jsonify({"error": f"field not allowed: {field}"}), 400
    conn = get_db()
    conn.execute(f"UPDATE dbo.SCHOOLS SET {field} = ? WHERE SCHOOL_KEY = ?", [value, school_key])
    conn.commit()
    return jsonify({"ok": True})


@mrb_bp.route("/api/schools/create", methods=["POST"])
@login_required
def api_schools_create():
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    name = (data.get("school_name") or "").strip()
    if not name:
        return jsonify({"error": "school_name required"}), 400
    conn = get_db()
    cur = conn.execute("SELECT ISNULL(MAX(SCHOOL_KEY), 0) + 1 FROM dbo.SCHOOLS")
    next_key = cur.fetchone()[0]
    conn.execute("""
        INSERT INTO dbo.SCHOOLS (SCHOOL_KEY, SCHOOL_NAME, FLAG_ACTIVE)
        VALUES (?, ?, 1)
    """, [next_key, name])
    conn.commit()
    return jsonify({"ok": True, "school_key": next_key})


# ── API: Floor Plans ───────────────────────────────────────────────────────────

_FP_ALLOWED_FIELDS = {
    "FLOORPLAN_NAME", "FLOORPLAN_TYPE", "COMPARE_AS_FLOORPLAN_TYPE",
    "FLOORPLAN_BEDS", "FLOORPLAN_BATHS", "FLOORPLAN_ORDER",
    "APARTMENT_COUNT", "BED_COUNT", "BEDS_FURNISHED", "APARTMENT_SQFT",
    "FLAG_SOLD_OUT", "FLAG_DOUBLE_OCC", "FLAG_EXCLUDE",
    "FLAG_FURNITURE_FEE_RR", "FLAG_UTILITY_CAP", "FLAG_UTILITY_CAP_RR", "FLAG_WATER_FEE_RR",
    "FURNITURE_FEE", "UTILITY_CAP", "WATER_FEE",
    "UNIT_PREMIUM_1_NAME", "UNIT_PREMIUM_1_AMOUNT", "UNIT_PREMIUM_1_WAIVED",
    "UNIT_PREMIUM_2_NAME", "UNIT_PREMIUM_2_AMOUNT", "UNIT_PREMIUM_2_WAIVED",
    "UNIT_PREMIUM_3_NAME", "UNIT_PREMIUM_3_AMOUNT", "UNIT_PREMIUM_3_WAIVED",
    "UNIT_PREMIUM_4_NAME", "UNIT_PREMIUM_4_AMOUNT", "UNIT_PREMIUM_4_WAIVED",
    "UNIT_PREMIUM_5_NAME", "UNIT_PREMIUM_5_AMOUNT", "UNIT_PREMIUM_5_WAIVED",
    "SUMMARY_FLOORPLAN", "SUMMARY_CONCESSIONS", "SUMMARY_GIFT_INCENTIVES",
    "SUMMARY_PRELEASE_SPECIALS", "SUMMARY_CURRENT_TERM_SPECIALS", "SUMMARY_REFERRALS",
    "FLAG_ACTIVE",
}


@mrb_bp.route("/api/floorplans")
@login_required
def api_floorplans():
    check = _require_access()
    if check:
        return check
    property_key = request.args.get("property_key", type=int)
    show_inactive = request.args.get("show_inactive", "0") == "1"
    if not property_key:
        return jsonify([])
    conn = get_db()
    sql = """
        SELECT FLOORPLAN_ASSIGNMENT_KEY, FLOORPLAN_NAME, FLOORPLAN_TYPE,
               COMPARE_AS_FLOORPLAN_TYPE, APARTMENT_COUNT, BED_COUNT,
               BEDS_FURNISHED, APARTMENT_SQFT, FLOORPLAN_BEDS, FLOORPLAN_BATHS,
               FLOORPLAN_ORDER, FLAG_ACTIVE, FLAG_SOLD_OUT, FLAG_DOUBLE_OCC,
               FLAG_EXCLUDE, FLAG_FURNITURE_FEE_RR, FLAG_UTILITY_CAP,
               FLAG_UTILITY_CAP_RR, FLAG_WATER_FEE_RR,
               FURNITURE_FEE, UTILITY_CAP, WATER_FEE,
               UNIT_PREMIUM_1_NAME, UNIT_PREMIUM_1_AMOUNT, UNIT_PREMIUM_1_WAIVED,
               UNIT_PREMIUM_2_NAME, UNIT_PREMIUM_2_AMOUNT, UNIT_PREMIUM_2_WAIVED,
               UNIT_PREMIUM_3_NAME, UNIT_PREMIUM_3_AMOUNT, UNIT_PREMIUM_3_WAIVED,
               UNIT_PREMIUM_4_NAME, UNIT_PREMIUM_4_AMOUNT, UNIT_PREMIUM_4_WAIVED,
               UNIT_PREMIUM_5_NAME, UNIT_PREMIUM_5_AMOUNT, UNIT_PREMIUM_5_WAIVED,
               SUMMARY_FLOORPLAN, SUMMARY_CONCESSIONS, SUMMARY_GIFT_INCENTIVES,
               SUMMARY_PRELEASE_SPECIALS, SUMMARY_CURRENT_TERM_SPECIALS,
               SUMMARY_REFERRALS, MODIFIED_BY, DATE_MODIFIED
        FROM dbo.FLOORPLAN_WORKSPACE
        WHERE PROPERTY_KEY = ?
    """
    params = [property_key]
    if not show_inactive:
        sql += " AND FLAG_ACTIVE = 1"
    sql += " ORDER BY FLOORPLAN_ORDER, FLOORPLAN_NAME"
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()

    def _ser(v):
        if hasattr(v, 'strftime'):
            return str(v)
        if hasattr(v, '__float__'):
            return float(v)
        return v

    return jsonify([{c: _ser(r[i]) for i, c in enumerate(cols)} for r in rows])


@mrb_bp.route("/api/floorplans/update", methods=["POST"])
@login_required
def api_floorplans_update():
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    key = data.get("floorplan_assignment_key")
    field = data.get("field")
    value = data.get("value")
    if key is None or not field:
        return jsonify({"error": "missing params"}), 400
    if field not in _FP_ALLOWED_FIELDS:
        return jsonify({"error": f"field not allowed: {field}"}), 400
    modified_by = _get_modified_by()
    conn = get_db()
    conn.execute(f"""
        UPDATE dbo.FLOORPLAN_WORKSPACE
        SET {field} = ?, MODIFIED_BY = ?, DATE_MODIFIED = CONVERT(INT, CONVERT(VARCHAR, GETDATE(), 112))
        WHERE FLOORPLAN_ASSIGNMENT_KEY = ?
    """, [value, modified_by, key])
    conn.commit()
    return jsonify({"ok": True})


@mrb_bp.route("/api/floorplans/create", methods=["POST"])
@login_required
def api_floorplans_create():
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    property_key = data.get("property_key")
    name = (data.get("floorplan_name") or "").strip()
    fp_type = (data.get("floorplan_type") or "").strip()
    if not property_key or not name:
        return jsonify({"error": "property_key and floorplan_name required"}), 400
    modified_by = _get_modified_by()
    conn = get_db()
    cur = conn.execute("SELECT ISNULL(MAX(FLOORPLAN_ASSIGNMENT_KEY), 0) + 1 FROM dbo.FLOORPLAN_WORKSPACE")
    next_key = cur.fetchone()[0]
    conn.execute("""
        INSERT INTO dbo.FLOORPLAN_WORKSPACE
            (FLOORPLAN_ASSIGNMENT_KEY, PROPERTY_KEY, FLOORPLAN_NAME, FLOORPLAN_TYPE,
             FLAG_ACTIVE, FLAG_SOLD_OUT, FLAG_DOUBLE_OCC, FLAG_EXCLUDE,
             MODIFIED_BY, DATE_MODIFIED)
        VALUES (?, ?, ?, ?, 1, 0, 0, 0, ?, CONVERT(INT, CONVERT(VARCHAR, GETDATE(), 112)))
    """, [next_key, property_key, name, fp_type, modified_by])
    conn.commit()
    return jsonify({"ok": True, "floorplan_assignment_key": next_key})


@mrb_bp.route("/api/floorplans/activate", methods=["POST"])
@login_required
def api_floorplans_activate():
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    key = data.get("floorplan_assignment_key")
    active = data.get("active")
    if key is None or active is None:
        return jsonify({"error": "missing params"}), 400
    modified_by = _get_modified_by()
    conn = get_db()
    conn.execute("""
        UPDATE dbo.FLOORPLAN_WORKSPACE
        SET FLAG_ACTIVE = ?, MODIFIED_BY = ?,
            DATE_MODIFIED = CONVERT(INT, CONVERT(VARCHAR, GETDATE(), 112))
        WHERE FLOORPLAN_ASSIGNMENT_KEY = ?
    """, [active, modified_by, key])
    conn.commit()
    return jsonify({"ok": True})


# ── API: Assign Comps ──────────────────────────────────────────────────────────

def _get_subject_id(conn, parent_key):
    """Resolve MktSrv_CompMap subjectID from PARENT_PROPERTY_KEY via COMP_ASSIGNMENTS."""
    row = conn.execute("""
        SELECT TOP 1 SUBJECTID
        FROM dbo.COMP_ASSIGNMENTS
        WHERE PARENT_PROPERTY_KEY = ? AND SUBJECTID IS NOT NULL
        ORDER BY DATE_KEY DESC
    """, [parent_key]).fetchone()
    return row[0] if row else None


@mrb_bp.route("/api/assign-comps")
@login_required
def api_assign_comps():
    check = _require_access()
    if check:
        return check
    parent_key = request.args.get("parent_key", type=int)
    date_key   = request.args.get("date_key",   type=int)
    if not parent_key or not date_key:
        return jsonify([])
    conn = get_db()
    rows = conn.execute("""
        SELECT PARENT_COMP_KEY, COMP_PROPERTY_KEY, COMP_PROPERTY_NAME,
               MARKET_CITY_STATE, RANK_ORDER, FLAG_PARENT, STARTCOMPDATE
        FROM dbo.COMP_ASSIGNMENTS
        WHERE PARENT_PROPERTY_KEY = ? AND DATE_KEY = ?
        ORDER BY RANK_ORDER
    """, [parent_key, date_key]).fetchall()
    result = []
    for r in rows:
        sd = str(r[6]) if r[6] and r[6] > 1 else None
        result.append({
            "parent_comp_key":   r[0],
            "comp_property_key": r[1],
            "comp_name":         r[2],
            "market":            r[3],
            "rank_order":        r[4],
            "flag_parent":       r[5],
            "start_date": f"{sd[:4]}-{sd[4:6]}-{sd[6:8]}" if sd else None,
        })
    return jsonify(result)


@mrb_bp.route("/api/assign-comps/add", methods=["POST"])
@login_required
def api_assign_comps_add():
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    parent_key = data.get("parent_key")
    comp_key   = data.get("comp_key")
    date_key   = data.get("date_key")
    if not parent_key or not comp_key or not date_key:
        return jsonify({"error": "missing params"}), 400

    parent_comp_key = f"{parent_key}.{comp_key}"
    modified_by = _get_modified_by()
    conn = get_db()

    existing = conn.execute(
        "SELECT 1 FROM dbo.COMP_ASSIGNMENTS WHERE PARENT_COMP_KEY = ? AND DATE_KEY = ?",
        [parent_comp_key, date_key]
    ).fetchone()
    if existing:
        return jsonify({"ok": True, "already_assigned": True})

    cp = conn.execute("""
        SELECT PROPERTY_NAME, MARKET_KEY, MARKET_CITY, MARKET_CITY_STATE, MARKET_STATE
        FROM dbo.COMP_PROPERTY WHERE PROPERTY_KEY = ?
    """, [comp_key]).fetchone()
    if not cp:
        return jsonify({"error": "comp not found"}), 404

    parent_row = conn.execute(
        "SELECT PROPERTY_NAME FROM dbo.PROPERTY_0 WHERE PROPERTY_KEY = ?", [parent_key]
    ).fetchone()
    parent_name = parent_row[0] if parent_row else ""

    max_rank = conn.execute(
        "SELECT ISNULL(MAX(RANK_ORDER), 0) FROM dbo.COMP_ASSIGNMENTS WHERE PARENT_PROPERTY_KEY = ? AND DATE_KEY = ?",
        [parent_key, date_key]
    ).fetchone()[0]

    today_int = int(date.today().strftime("%Y%m%d"))
    conn.execute("""
        INSERT INTO dbo.COMP_ASSIGNMENTS
            (PARENT_COMP_KEY, DATE_KEY, COMP_PROPERTY_KEY, COMP_PROPERTY_NAME,
             PARENT_PROPERTY_KEY, PARENT_PROPERTY_NAME,
             MARKET_KEY, MARKET_CITY, MARKET_CITY_STATE, MARKET_STATE,
             FLAG_COMP, FLAG_PARENT, FLAG_PARENT_1,
             RANK_ORDER, ENDCOMPDATE, STARTCOMPDATE, MODIFIEDBY, MODIFIEDDATE)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 0, ?, 20991231, ?, ?, ?)
    """, [
        parent_comp_key, date_key, comp_key, cp[0],
        parent_key, parent_name,
        cp[1], cp[2], cp[3], cp[4],
        max_rank + 1, date_key, modified_by, today_int
    ])
    conn.commit()
    return jsonify({"ok": True, "rank_order": max_rank + 1})


@mrb_bp.route("/api/assign-comps/remove", methods=["POST"])
@login_required
def api_assign_comps_remove():
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    parent_comp_key = data.get("parent_comp_key")
    date_key        = data.get("date_key")
    if not parent_comp_key or not date_key:
        return jsonify({"error": "missing params"}), 400
    conn = get_db()
    conn.execute(
        "DELETE FROM dbo.COMP_ASSIGNMENTS WHERE PARENT_COMP_KEY = ? AND DATE_KEY = ?",
        [parent_comp_key, date_key]
    )
    conn.commit()
    return jsonify({"ok": True})


@mrb_bp.route("/api/assign-comps/reorder", methods=["POST"])
@login_required
def api_assign_comps_reorder():
    check = _require_access()
    if check:
        return check
    data = request.get_json()
    orders   = data.get("orders", [])
    date_key = data.get("date_key")
    if not orders or not date_key:
        return jsonify({"error": "missing params"}), 400
    conn = get_db()
    for o in orders:
        conn.execute(
            "UPDATE dbo.COMP_ASSIGNMENTS SET RANK_ORDER = ? WHERE PARENT_COMP_KEY = ? AND DATE_KEY = ?",
            [o["rank_order"], o["parent_comp_key"], date_key]
        )
    conn.commit()
    return jsonify({"ok": True})
