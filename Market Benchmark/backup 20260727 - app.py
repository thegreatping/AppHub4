"""Market Benchmark — Standalone dev server (port 5060)."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")

from flask import Flask, render_template, jsonify, request, session
from helpers import load_env, SafeConnection
from datetime import date, timedelta

app = Flask(__name__)
app.secret_key = "mrb-dev-key"

_env = None


def get_env():
    global _env
    if _env is None:
        _env = load_env()
    return _env


def get_db():
    """Get a connection to DB_APP_SUPPORT (direct)."""
    return SafeConnection(get_env(), "DB_APP_SUPPORT", None, direct=True)


# ── Pages ───────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ── API: Parent Properties ──────────────────────────────────────────────────────

@app.route("/api/parent-properties")
def api_parent_properties():
    """Return list of parent properties for the dropdown."""
    conn = get_db()
    rows = conn.execute("""
        SELECT PROPERTY_KEY, PROPERTY_NAME, MARKET_KEY
        FROM dbo.PROPERTY_0
        WHERE FLAG_REPORTABLE = 1 AND FLAG_DISPOSITIONED = 0
        ORDER BY PROPERTY_NAME
    """).fetchall()
    return jsonify([{"key": r[0], "name": r[1], "market_key": r[2]} for r in rows])


# ── API: Weeks ──────────────────────────────────────────────────────────────────

@app.route("/api/weeks")
def api_weeks():
    """Return available weeks filtered by AY, only up to current week (< next Monday)."""
    ay = request.args.get("ay", type=int, default=2026)
    conn = get_db()
    # Calculate next Monday as YYYYMMDD integer
    from datetime import date, timedelta
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


# ── API: Markets (for dropdowns) ────────────────────────────────────────────────

@app.route("/api/markets")
def api_markets():
    """Return all markets with non-empty names."""
    conn = get_db()
    rows = conn.execute("""
        SELECT MARKET_KEY, MARKET_CITY_STATE
        FROM dbo.MARKETS
        WHERE MARKET_CITY_STATE IS NOT NULL AND MARKET_CITY_STATE != ''
        ORDER BY MARKET_CITY_STATE
    """).fetchall()
    return jsonify([{"key": r[0], "name": r[1]} for r in rows])


@app.route("/api/markets/all")
def api_markets_all():
    """Return all markets (full detail) for CRUD."""
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


@app.route("/api/markets/update", methods=["POST"])
def api_markets_update():
    """Update a single field on a MARKETS row."""
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


@app.route("/api/markets/create", methods=["POST"])
def api_markets_create():
    """Create a new market record."""
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


@app.route("/api/markets/delete", methods=["POST"])
def api_markets_delete():
    """Delete a market record."""
    data = request.get_json()
    market_key = data.get("market_key")
    if market_key is None:
        return jsonify({"error": "missing market_key"}), 400
    conn = get_db()
    conn.execute("DELETE FROM dbo.MARKETS WHERE MARKET_KEY = ?", [market_key])
    conn.commit()
    return jsonify({"ok": True})


# ── API: Comp Properties ──────────────────────────────────────────────────────────

@app.route("/api/comp-properties")
def api_comp_properties():
    """Return comp properties for CRUD grid."""
    q = request.args.get("q", "").strip()
    show_inactive = request.args.get("inactive", "0") == "1"
    conn = get_db()
    where = "WHERE PROPERTY_NAME LIKE ?" if q else ("WHERE FLAG_ACTIVE = 1" if not show_inactive else "")
    params = [f"%{q}%"] if q else []
    cur = conn.execute(f"""
        SELECT PROPERTY_KEY, PROPERTY_NAME, ADDRESS_1, ADDRESS_CITY, ADDRESS_STATE,
               ADDRESS_ZIP, COMPANY, OWNER, MARKET_KEY, MARKET_CITY_STATE,
               BED_COUNT_STATIC, APARTMENT_COUNT, BUILD_YEAR, DISTANCE_TO_CAMPUS,
               ASSET_CLASS, FLAG_ACTIVE, FLAG_COMP, FLAG_PARENT, URL_WEBSITE
        FROM dbo.COMP_PROPERTY
        {where}
        ORDER BY PROPERTY_NAME
    """, params)
    cols = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    return jsonify([dict(zip(cols, row)) for row in rows])


@app.route("/api/comp-properties/update", methods=["POST"])
def api_comp_properties_update():
    """Update a single field on a COMP_PROPERTY row."""
    data = request.get_json()
    pk = data.get("property_key")
    field = data.get("field")
    value = data.get("value")
    if pk is None or not field:
        return jsonify({"error": "missing params"}), 400
    # Broad whitelist for the detail panel — validate is alphanumeric/underscore
    import re
    blocked = {"PROPERTY_KEY", "DATE_CREATED"}
    if field in blocked or not re.match(r'^[A-Z_0-9]+$', field):
        return jsonify({"error": f"field not allowed: {field}"}), 400
    conn = get_db()
    conn.execute(f"UPDATE dbo.COMP_PROPERTY SET {field} = ? WHERE PROPERTY_KEY = ?", [value, pk])
    conn.commit()
    return jsonify({"ok": True})


@app.route("/api/comp-properties/detail")
def api_comp_properties_detail():
    """Return ALL columns for a single comp property (for slide-out detail)."""
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


@app.route("/api/comp-properties/create", methods=["POST"])
def api_comp_properties_create():
    """Create a new comp property."""
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


# ── API: Comp Assignments (for selected parent + week) ─────────────────────────

@app.route("/api/comp-assignments")
def api_comp_assignments():
    """Return comp assignments for a parent property + week."""
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


# ── API: Comp Fact (for selected comp + week) ──────────────────────────────────

@app.route("/api/comp-fact")
def api_comp_fact():
    """Return COMP_FACT row for a comp property + week."""
    property_key = request.args.get("property_key", type=int)
    date_key = request.args.get("date_key", type=int)
    if not property_key or not date_key:
        return jsonify([])
    conn = get_db()
    cur = conn.execute("""
        SELECT *
        FROM dbo.COMP_FACT
        WHERE PROPERTY_KEY = ? AND DATE_KEY = ?
    """, [property_key, date_key])
    cols = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    return jsonify([dict(zip(cols, row)) for row in rows])


# ── API: Floorplan Fact (for selected comp + week) ─────────────────────────────

@app.route("/api/floorplan-fact")
def api_floorplan_fact():
    """Return FLOORPLAN_FACT rows for a comp property + week."""
    property_key = request.args.get("property_key", type=int)
    date_key = request.args.get("date_key", type=int)
    if not property_key or not date_key:
        return jsonify([])
    conn = get_db()
    cur = conn.execute("""
        SELECT *
        FROM dbo.FLOORPLAN_FACT
        WHERE PROPERTY_KEY = ? AND DATE_KEY = ? AND FLAG_ACTIVE = 1
        ORDER BY FLOORPLAN_NAME
    """, [property_key, date_key])
    cols = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    return jsonify([dict(zip(cols, row)) for row in rows])


# ── API: Save Floorplan Fact field ──────────────────────────────────────────

@app.route("/api/floorplan-fact/update", methods=["POST"])
def api_floorplan_fact_update():
    """Update a single field on a FLOORPLAN_FACT row."""
    data = request.get_json()
    key = data.get("floorplan_assignment_key")
    date_key = data.get("date_key")
    field = data.get("field")
    value = data.get("value")
    if not key or not date_key or not field:
        return jsonify({"error": "missing params"}), 400

    # Whitelist allowed fields
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


# ── API: Save Comp Fact field ───────────────────────────────────────────────

@app.route("/api/comp-fact/update", methods=["POST"])
def api_comp_fact_update():
    """Update a single field on a COMP_FACT row."""
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

@app.route("/api/schools")
def api_schools():
    """Return all schools (optionally filtered by search query)."""
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
            WHERE FLAG_ACTIVE = 1
            ORDER BY SCHOOL_NAME
        """)
    cols = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    return jsonify([dict(zip(cols, row)) for row in rows])


@app.route("/api/schools/update", methods=["POST"])
def api_schools_update():
    """Update a single field on a SCHOOLS row."""
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
    conn.execute(f"""
        UPDATE dbo.SCHOOLS SET {field} = ? WHERE SCHOOL_KEY = ?
    """, [value, school_key])
    conn.commit()
    return jsonify({"ok": True})


@app.route("/api/schools/create", methods=["POST"])
def api_schools_create():
    """Create a new school record."""
    data = request.get_json()
    name = (data.get("school_name") or "").strip()
    if not name:
        return jsonify({"error": "school_name required"}), 400

    conn = get_db()
    # Get next key
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


@app.route("/api/floorplans")
def api_floorplans():
    """Return FLOORPLAN_WORKSPACE rows for a parent property."""
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


@app.route("/api/floorplans/update", methods=["POST"])
def api_floorplans_update():
    """Update a single field on a FLOORPLAN_WORKSPACE row."""
    data = request.get_json()
    key = data.get("floorplan_assignment_key")
    field = data.get("field")
    value = data.get("value")
    if key is None or not field:
        return jsonify({"error": "missing params"}), 400
    if field not in _FP_ALLOWED_FIELDS:
        return jsonify({"error": f"field not allowed: {field}"}), 400
    user_info = session.get("user") or {}
    modified_by = user_info.get("name", "MRB-App") if isinstance(user_info, dict) else "MRB-App"
    conn = get_db()
    conn.execute(f"""
        UPDATE dbo.FLOORPLAN_WORKSPACE
        SET {field} = ?, MODIFIED_BY = ?, DATE_MODIFIED = CONVERT(INT, CONVERT(VARCHAR, GETDATE(), 112))
        WHERE FLOORPLAN_ASSIGNMENT_KEY = ?
    """, [value, modified_by, key])
    conn.commit()
    return jsonify({"ok": True})


@app.route("/api/floorplans/create", methods=["POST"])
def api_floorplans_create():
    """Create a new FLOORPLAN_WORKSPACE row."""
    data = request.get_json()
    property_key = data.get("property_key")
    name = (data.get("floorplan_name") or "").strip()
    fp_type = (data.get("floorplan_type") or "").strip()
    if not property_key or not name:
        return jsonify({"error": "property_key and floorplan_name required"}), 400
    user_info = session.get("user") or {}
    modified_by = user_info.get("name", "MRB-App") if isinstance(user_info, dict) else "MRB-App"
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


@app.route("/api/floorplans/activate", methods=["POST"])
def api_floorplans_activate():
    """Toggle FLAG_ACTIVE on a FLOORPLAN_WORKSPACE row."""
    data = request.get_json()
    key = data.get("floorplan_assignment_key")
    active = data.get("active")  # 1 or 0
    if key is None or active is None:
        return jsonify({"error": "missing params"}), 400
    user_info = session.get("user") or {}
    modified_by = user_info.get("name", "MRB-App") if isinstance(user_info, dict) else "MRB-App"
    conn = get_db()
    conn.execute("""
        UPDATE dbo.FLOORPLAN_WORKSPACE
        SET FLAG_ACTIVE = ?, MODIFIED_BY = ?,
            DATE_MODIFIED = CONVERT(INT, CONVERT(VARCHAR, GETDATE(), 112))
        WHERE FLOORPLAN_ASSIGNMENT_KEY = ?
    """, [active, modified_by, key])
    conn.commit()
    return jsonify({"ok": True})


# ── API: Assign Comps (via COMP_ASSIGNMENTS + MktSrv_CompMap) ─────────────────

def _get_subject_id(conn, parent_key):
    """Resolve MktSrv_CompMap subjectID from PARENT_PROPERTY_KEY using
    COMP_ASSIGNMENTS — the same projection table the rest of the app uses."""
    row = conn.execute("""
        SELECT TOP 1 SUBJECTID
        FROM dbo.COMP_ASSIGNMENTS
        WHERE PARENT_PROPERTY_KEY = ? AND SUBJECTID IS NOT NULL
        ORDER BY DATE_KEY DESC
    """, [parent_key]).fetchone()
    return row[0] if row else None


@app.route("/api/assign-comps")
def api_assign_comps():
    """Return current comp assignments for a parent property.
    Reads directly from MktSrv_CompMap (live source) so newly added/removed
    comps are immediately reflected without waiting for the projector SP."""
    parent_key = request.args.get("parent_key", type=int)
    if not parent_key:
        return jsonify([])
    conn = get_db()

    # Resolve subjectID via COMP_ASSIGNMENTS history
    subject_id = _get_subject_id(conn, parent_key)
    if subject_id is None:
        return jsonify([])

    # Include the parent property itself (rank 0) by querying COMP_PROPERTY
    # for the parent row, then union with the live MktSrv_CompMap assignments
    rows = conn.execute("""
        SELECT
            m.marketCompMapID AS map_id,
            m.subjectID       AS subject_id,
            m.compID          AS comp_id,
            cp.PROPERTY_NAME  AS comp_name,
            cp.PROPERTY_KEY   AS property_key,
            m.orderID         AS order_id,
            cp.MARKET_CITY_STATE AS market,
            m.startCompDate,
            m.endCompDate,
            m.modifiedBy,
            m.modifiedDate
        FROM dbo.MktSrv_CompMap m
        JOIN dbo.COMP_PROPERTY cp ON (
            cp.LEGACY_MARKETPROPERTYID = m.compID
            OR (cp.LEGACY_MARKETPROPERTYID IS NULL AND cp.PROPERTY_KEY = m.compID)
        )
        WHERE m.subjectID = ?
          AND m.endCompDate > GETDATE()
        ORDER BY m.orderID
    """, [subject_id]).fetchall()

    result = []

    # Prepend the parent property itself as rank-0 (it lives in PROPERTY_0,
    # not MktSrv_CompMap, so we fetch it separately)
    parent_row = conn.execute("""
        SELECT p.PROPERTY_KEY, p.PROPERTY_NAME, mk.MARKET_CITY_STATE
        FROM dbo.PROPERTY_0 p
        LEFT JOIN dbo.MARKETS mk ON mk.MARKET_KEY = p.MARKET_KEY
        WHERE p.PROPERTY_KEY = ?
    """, [parent_key]).fetchone()
    if parent_row:
        result.append({
            "map_id": None,
            "subject_id": subject_id,
            "comp_id": parent_row[0],
            "comp_name": parent_row[1],
            "order_id": 0,
            "market": parent_row[2],
            "start_date": None,
            "end_date": None,
            "modified_by": None,
            "modified_date": None,
        })

    for r in rows:
        result.append({
            "map_id":   r[0],
            "subject_id": r[1],
            "comp_id":  r[4],   # PROPERTY_KEY (real key the JS uses for ghosting)
            "legacy_comp_id": r[2],  # LEGACY_MARKETPROPERTYID (used in MktSrv_CompMap)
            "comp_name": r[3],
            "order_id": r[5],
            "market":   r[6],
            "start_date": r[7].strftime("%Y-%m-%d") if r[7] else None,
            "end_date":   r[8].strftime("%Y-%m-%d") if r[8] else None,
            "modified_by": r[9],
            "modified_date": r[10].strftime("%Y-%m-%d") if r[10] else None,
        })

    return jsonify(result)


@app.route("/api/assign-comps/add", methods=["POST"])
def api_assign_comps_add():
    """Add a new comp assignment to MktSrv_CompMap."""
    data = request.get_json()
    parent_key = data.get("parent_key")
    comp_key = data.get("comp_key")
    date_key = data.get("date_key")  # YYYYMMDD int
    if not parent_key or not comp_key:
        return jsonify({"error": "missing params"}), 400

    if date_key:
        dk = str(date_key)
        start_date = f"{dk[:4]}-{dk[4:6]}-{dk[6:8]}"
    else:
        start_date = date.today().strftime("%Y-%m-%d")

    end_date = "2099-12-31"
    user_info = session.get("user") or {}
    modified_by = user_info.get("name", "MRB-App") if isinstance(user_info, dict) else "MRB-App"

    conn = get_db()
    # Resolve the subjectID the same way the projection was built
    subject_id = _get_subject_id(conn, parent_key)
    if subject_id is None:
        return jsonify({"error": "cannot resolve subjectID for this parent property"}), 400

    # comp_key is PROPERTY_KEY — resolve the legacy MARKETPROPERTYID that MktSrv_CompMap uses.
    # For newer properties without a legacy ID, fall back to using PROPERTY_KEY directly.
    legacy_row = conn.execute("""
        SELECT LEGACY_MARKETPROPERTYID FROM dbo.COMP_PROPERTY WHERE PROPERTY_KEY = ?
    """, [comp_key]).fetchone()
    legacy_comp_id = (legacy_row[0] if legacy_row and legacy_row[0] is not None else comp_key)

    # Prevent duplicate: if this comp is already actively assigned, do nothing
    existing = conn.execute("""
        SELECT marketCompMapID FROM dbo.MktSrv_CompMap
        WHERE subjectID = ? AND compID = ? AND endCompDate > GETDATE()
    """, [subject_id, legacy_comp_id]).fetchone()
    if existing:
        return jsonify({"ok": True, "already_assigned": True})

    # Compute next marketCompMapID (not an identity column)
    cur = conn.execute("SELECT ISNULL(MAX(marketCompMapID), 0) + 1 FROM dbo.MktSrv_CompMap")
    next_map_id = cur.fetchone()[0]

    cur = conn.execute("""
        SELECT ISNULL(MAX(orderID), -1) + 1
        FROM dbo.MktSrv_CompMap
        WHERE subjectID = ? AND endCompDate > GETDATE()
    """, [subject_id])
    next_order = cur.fetchone()[0]

    conn.execute("""
        INSERT INTO dbo.MktSrv_CompMap
            (marketCompMapID, subjectID, compID, orderID, startCompDate, endCompDate, modifiedBy, modifiedDate)
        VALUES (?, ?, ?, ?, ?, ?, ?, GETDATE())
    """, [next_map_id, subject_id, legacy_comp_id, next_order, start_date, end_date, modified_by])
    conn.commit()
    return jsonify({"ok": True, "order_id": next_order})


@app.route("/api/assign-comps/remove", methods=["POST"])
def api_assign_comps_remove():
    """Soft-delete a comp assignment by setting endCompDate to yesterday."""
    data = request.get_json()
    map_id = data.get("map_id")
    if not map_id:
        return jsonify({"error": "missing map_id"}), 400
    user_info = session.get("user") or {}
    modified_by = user_info.get("name", "MRB-App") if isinstance(user_info, dict) else "MRB-App"
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    conn = get_db()
    conn.execute("""
        UPDATE dbo.MktSrv_CompMap
        SET endCompDate = ?, modifiedBy = ?, modifiedDate = GETDATE()
        WHERE marketCompMapID = ?
    """, [yesterday, modified_by, map_id])
    conn.commit()
    return jsonify({"ok": True})


@app.route("/api/assign-comps/reorder", methods=["POST"])
def api_assign_comps_reorder():
    """Update orderID for a list of comp assignments after drag-to-reorder."""
    data = request.get_json()
    orders = data.get("orders", [])  # [{map_id, order_id}, ...]
    if not orders:
        return jsonify({"error": "no orders"}), 400
    user_info = session.get("user") or {}
    modified_by = user_info.get("name", "MRB-App") if isinstance(user_info, dict) else "MRB-App"
    conn = get_db()
    for o in orders:
        conn.execute("""
            UPDATE dbo.MktSrv_CompMap
            SET orderID = ?, modifiedBy = ?, modifiedDate = GETDATE()
            WHERE marketCompMapID = ?
        """, [o["order_id"], modified_by, o["map_id"]])
    conn.commit()
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True, port=5055)
