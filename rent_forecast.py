"""Rent Forecasting System (RFS) module — reforecast rent tiers by property/floorplan."""
import os
from flask import Blueprint, render_template, session, jsonify, request
from auth import login_required
from modules import MODULES, APP_ID_MAP
import sys
import datetime
from decimal import Decimal

from helpers import load_env, SafeConnection

rfs_bp = Blueprint("rfs", __name__, url_prefix="/rfs")

_env = None


def _clean_row(row):
    """Convert Decimal/date values to JSON-safe types."""
    return {k: (float(v) if isinstance(v, Decimal) else v) for k, v in row.items()}



def _get_env():
    global _env
    if _env is None:
        _env = load_env()
    return _env


def _require_access():
    """Check that the current user has access to RFS (app_id=7)."""
    if os.environ.get("DEV_BYPASS", "").lower() == "true":
        return None
    if session.get("is_developer"):
        return None
    user_modules = session.get("user_modules", [])
    for m in user_modules:
        if m["id"] == 7:
            return None
    return jsonify({"error": "unauthorized"}), 403


def _get_user_email():
    return (session.get("user") or {}).get("email", "").lower()


def _get_security_level():
    return session.get("security_level", 0)


# ─── PAGE ROUTE ─────────────────────────────────────────────────────────────────

@rfs_bp.route("/")
@login_required
def index():
    """Render the RFS page within the shell framework."""
    check = _require_access()
    if check:
        return check
    from config import APP_VERSION
    user_modules = session.get("user_modules", [])
    allowed_string_ids = set()
    for m in user_modules:
        string_id = APP_ID_MAP.get(m["id"])
        if string_id:
            allowed_string_ids.add(string_id)
    visible = [m for m in MODULES if m["id"] in allowed_string_ids] if user_modules else MODULES
    return render_template("rent_forecast.html",
                           modules=visible,
                           active_module="rent_forecasting_system",
                           user=session.get("user", {}),
                           is_developer=session.get("is_developer", False),
                           is_dev_mode=session.get("is_dev_mode", False),
                           is_impersonating=session.get("is_impersonating", False),
                           impersonating_user=session.get("impersonating_user", None),
                           version=APP_VERSION)


# ─── API: PROPERTIES LIST ───────────────────────────────────────────────────────

@rfs_bp.route("/api/properties")
@login_required
def get_properties():
    """Return properties available for rent forecasting (security-filtered)."""
    check = _require_access()
    if check:
        return check

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        cur = conn.execute("""
            SELECT DISTINCT f.PROPERTY_KEY, p.PROPERTY_NAME,
                   p.PM_EMAIL, p.RM_EMAIL, p.BED_COUNT_COMPILED
            FROM dbo.FORECAST_FORECASTS f
            JOIN dbo.PROPERTY_0 p ON p.PROPERTY_KEY = f.PROPERTY_KEY
            WHERE f.PROPERTY_KEY IS NOT NULL
            ORDER BY p.PROPERTY_NAME
        """)
        cols = [d[0] for d in cur.description]
        rows = [_clean_row(dict(zip(cols, r))) for r in cur.fetchall()]
    finally:
        conn.close()

    # Security filter based on user level
    user_email = _get_user_email()
    sec_level = _get_security_level()
    if sec_level > 50:
        return jsonify(rows)
    elif sec_level == 50:
        filtered = [r for r in rows if (r.get("PM_EMAIL") or "").lower() == user_email]
        return jsonify(filtered)
    else:
        return jsonify(rows)


# ─── API: FORECASTS FOR A PROPERTY ─────────────────────────────────────────────

@rfs_bp.route("/api/forecasts")
@login_required
def get_forecasts():
    """Return forecast plans for a given property."""
    check = _require_access()
    if check:
        return check

    property_key = request.args.get("property_key", type=int)
    if not property_key:
        return jsonify({"error": "property_key required"}), 400

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        cur = conn.execute("""
            SELECT FORECAST_KEY, FORECAST_NAME, AY, PROPERTY_KEY, PROPERTY_NAME,
                   FLAG_APPROVED, INDUCEMENT_PLANNED_USE, DATE_CREATED, DATE_MODIFIED
            FROM dbo.FORECAST_FORECASTS
            WHERE PROPERTY_KEY = ?
            ORDER BY FORECAST_NAME
        """, (property_key,))
        cols = [d[0] for d in cur.description]
        rows = [_clean_row(dict(zip(cols, r))) for r in cur.fetchall()]
    finally:
        conn.close()
    return jsonify(rows)


# ─── API: FLOORPLANS FOR A PROPERTY ────────────────────────────────────────────

@rfs_bp.route("/api/floorplans")
@login_required
def get_floorplans():
    """Return floorplans for a property."""
    check = _require_access()
    if check:
        return check

    property_key = request.args.get("property_key", type=int)
    ay = request.args.get("ay", type=int)
    if not property_key:
        return jsonify({"error": "property_key required"}), 400

    env = _get_env()
    conn = SafeConnection(env, "WH_STAGING", None, direct=True)
    try:
        # Source: FLOORPLANS_F (Power App uses "FLOORPLANS" — FLOORPLANS_F has friendly names)
        cur = conn.execute("""
            SELECT FLOORPLAN_KEY,
                   FLOORPLAN AS FLOORPLAN,
                   FLOORPLAN_CODE,
                   BEDS,
                   COMPARE_AS_FLOORPLAN_TYPE
            FROM dbo.FLOORPLANS_F
            WHERE PROPERTY_KEY = ? AND FLAG_REPORTABLE = 1
              AND FLOORPLAN <> 'DELETED TYPE'
            ORDER BY FLOORPLAN
        """, (property_key,))
        cols = [d[0] for d in cur.description]
        rows = [_clean_row(dict(zip(cols, r))) for r in cur.fetchall()]
    finally:
        conn.close()
    return jsonify(rows)


# ─── API: MARKET COMPS ──────────────────────────────────────────────────────────

@rfs_bp.route("/api/comps")
@login_required
def get_comps():
    """Return market comps for a forecast/property filtered by floorplan compare type."""
    check = _require_access()
    if check:
        return check

    forecast_key = request.args.get("forecast_key", type=int)
    property_key = request.args.get("property_key", type=int)
    compare_type = request.args.get("compare_type", "")

    if not all([forecast_key, property_key]):
        return jsonify({"error": "forecast_key and property_key required"}), 400

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        sql = """
            SELECT FLOORPLAN_ASSIGNMENT_KEY,
                   COMP_PROPERTY_NAME,
                   FLOORPLAN_NAME,
                   COMPARE_AS_FLOORPLAN_TYPE,
                   ISNULL(NER_PRELEASE_FURNISHED, 0) AS NER,
                   FLAG_SOLD_OUT,
                   FLAG_INCLUDE
            FROM dbo.FORECAST_COMP_FLOORPLANS
            WHERE FORECAST_KEY = ? AND PARENT_PROPERTY_KEY = ?
              AND COMP_PROPERTY_KEY <> PARENT_PROPERTY_KEY
        """
        params = [forecast_key, property_key]
        if compare_type:
            sql += " AND COMPARE_AS_FLOORPLAN_TYPE = ?"
            params.append(compare_type)
        sql += " ORDER BY FLAG_INCLUDE DESC, COMP_PROPERTY_NAME, FLOORPLAN_NAME"
        cur = conn.execute(sql, params)
        cols = [d[0] for d in cur.description]
        rows = [_clean_row(dict(zip(cols, r))) for r in cur.fetchall()]
    finally:
        conn.close()
    return jsonify(rows)


# ─── API: COMPS TOGGLE ─────────────────────────────────────────────────────────

@rfs_bp.route("/api/comps/toggle", methods=["POST"])
@login_required
def toggle_comp_include():
    """Toggle FLAG_INCLUDE for a single comp row."""
    check = _require_access()
    if check:
        return check

    data = request.get_json(force=True) or {}
    fak = data.get("floorplan_assignment_key")
    fk  = data.get("forecast_key")
    if not fak or not fk:
        return jsonify({"error": "floorplan_assignment_key and forecast_key required"}), 400

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute(
            "UPDATE dbo.FORECAST_COMP_FLOORPLANS "
            "SET FLAG_INCLUDE = 1 - FLAG_INCLUDE "
            "WHERE FLOORPLAN_ASSIGNMENT_KEY = ? AND FORECAST_KEY = ?",
            [fak, fk]
        )
        cur = conn.execute(
            "SELECT FLAG_INCLUDE FROM dbo.FORECAST_COMP_FLOORPLANS "
            "WHERE FLOORPLAN_ASSIGNMENT_KEY = ? AND FORECAST_KEY = ?",
            [fak, fk]
        )
        row = cur.fetchone()
        new_val = int(row[0]) if row else 0
    finally:
        conn.close()
    return jsonify({"FLAG_INCLUDE": new_val})


# ─── API: BUDGET TIERS ──────────────────────────────────────────────────────────

@rfs_bp.route("/api/budget-tiers")
@login_required
def get_budget_tiers():
    """Return budget tiers for a property/floorplan/AY/lease_type."""
    check = _require_access()
    if check:
        return check

    property_key = request.args.get("property_key", type=int)
    floorplan_key = request.args.get("floorplan_key", type=int)
    ay = request.args.get("ay", type=int)
    lease_type = request.args.get("lease_type", "RENEWAL")

    if not all([property_key, floorplan_key, ay]):
        return jsonify({"error": "property_key, floorplan_key, ay required"}), 400

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        cur = conn.execute("""
            SELECT TIER_NUMBER, BEDS, RATE, RATE_EXTENDED1, LEASE_TYPE
            FROM dbo.FORECAST_BUDGET_TIERS
            WHERE PROPERTY_KEY = ? AND FLOORPLAN_KEY = ? AND AY = ?
              AND LEASE_TYPE = ? AND TIER_NUMBER <> 0
            ORDER BY TIER_NUMBER
        """, (property_key, floorplan_key, ay, lease_type))
        cols = [d[0] for d in cur.description]
        rows = [_clean_row(dict(zip(cols, r))) for r in cur.fetchall()]
    finally:
        conn.close()
    return jsonify(rows)


# ─── API: LEFT TO BUDGET ───────────────────────────────────────────────────────

@rfs_bp.route("/api/left-to-budget")
@login_required
def get_left_to_budget():
    """Compute beds left to budget: BudgetTotal(R+N) - Actuals(R+N) - ForecastTiers(R+N)."""
    check = _require_access()
    if check:
        return check

    property_key = request.args.get("property_key", type=int)
    floorplan_key = request.args.get("floorplan_key", type=int)
    ay = request.args.get("ay", type=int)
    forecast_key = request.args.get("forecast_key", type=int)

    if not all([property_key, floorplan_key, ay]):
        return jsonify({"error": "property_key, floorplan_key, ay required"}), 400

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        # Budget total (both lease types)
        cur = conn.execute("""
            SELECT COALESCE(SUM(BEDS), 0) AS total
            FROM dbo.FORECAST_BUDGET_TIERS
            WHERE PROPERTY_KEY = ? AND FLOORPLAN_KEY = ? AND AY = ? AND TIER_NUMBER <> 0
        """, (property_key, floorplan_key, ay))
        budget_total = cur.fetchone()[0]

        # Actuals total (both lease types)
        cur = conn.execute("""
            SELECT COALESCE(SUM(LEASED_COUNT_RENT), 0) AS total
            FROM dbo.FLOORPLAN_ACTUALS_RENT
            WHERE PROPERTY_KEY = ? AND FLOORPLAN_KEY = ? AND AY = ?
        """, (property_key, floorplan_key, ay))
        actuals_total = cur.fetchone()[0]

        # Forecast tiers total (both lease types)
        forecast_total = 0
        if forecast_key:
            cur = conn.execute("""
                SELECT COALESCE(SUM(LEASE_COUNT), 0) AS total
                FROM dbo.FORECAST_FORECAST_TIERS
                WHERE FORECAST_KEY = ? AND FLOORPLAN_KEY = ?
            """, (forecast_key, floorplan_key))
            forecast_total = cur.fetchone()[0]
    finally:
        conn.close()

    left = budget_total - actuals_total - forecast_total
    return jsonify({"budget_total": budget_total, "actuals_total": actuals_total,
                    "forecast_total": forecast_total, "left_to_budget": left})


# ─── API: FORECAST TIERS (READ) ────────────────────────────────────────────────

@rfs_bp.route("/api/forecast-tiers")
@login_required
def get_forecast_tiers():
    """Return reforecast tiers for a forecast/floorplan/lease_type."""
    check = _require_access()
    if check:
        return check

    forecast_key = request.args.get("forecast_key", type=int)
    floorplan_key = request.args.get("floorplan_key", type=int)
    lease_type = request.args.get("lease_type", "RENEWAL")

    if not all([forecast_key, floorplan_key]):
        return jsonify({"error": "forecast_key, floorplan_key required"}), 400

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        cur = conn.execute("""
            SELECT FORECAST_TIERS_KEY, FORECAST_KEY, FLOORPLAN_KEY, FLOORPLAN_CODE,
                   PROPERTY_KEY, PROPERTY_NAME, LEASE_TYPE, TIER_ORDER,
                   LEASE_COUNT, RATE, RATE_EXTENDED, CONCESSION_AMOUNT,
                   CONCESSION_MONTHLY, CONCESSION_AMOUNT_EXTENDED,
                   NER, NER_EXTENDED, CREATED_BY, MODIFIED_BY,
                   DATE_CREATED, DATE_MODIFIED
            FROM dbo.FORECAST_FORECAST_TIERS
            WHERE FORECAST_KEY = ? AND FLOORPLAN_KEY = ? AND LEASE_TYPE = ?
            ORDER BY TIER_ORDER
        """, (forecast_key, floorplan_key, lease_type))
        cols = [d[0] for d in cur.description]
        rows = [_clean_row(dict(zip(cols, r))) for r in cur.fetchall()]
    finally:
        conn.close()
    return jsonify(rows)


# ─── API: SAVE FORECAST TIER ───────────────────────────────────────────────────

@rfs_bp.route("/api/forecast-tiers/save", methods=["POST"])
@login_required
def save_forecast_tier():
    """Update a single forecast tier row."""
    check = _require_access()
    if check:
        return check

    data = request.get_json()
    if not data or not data.get("forecast_tiers_key"):
        return jsonify({"error": "forecast_tiers_key required"}), 400

    tier_key = int(data["forecast_tiers_key"])
    tier_order = int(data.get("tier_order", 999))
    lease_count = int(data.get("lease_count", 0))
    rate = float(data.get("rate", 0))
    concession = float(data.get("concession_amount", 0))

    # Calculated fields
    rate_extended = rate * lease_count
    concession_monthly = concession / 12 if concession else 0
    concession_extended = concession * lease_count
    ner = rate - concession_monthly
    ner_extended = ner * lease_count

    user_email = _get_user_email()

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        cur = conn.execute("""
            UPDATE dbo.FORECAST_FORECAST_TIERS
            SET TIER_ORDER = ?,
                LEASE_COUNT = ?,
                RATE = ?,
                RATE_EXTENDED = ?,
                CONCESSION_AMOUNT = ?,
                CONCESSION_MONTHLY = ?,
                CONCESSION_AMOUNT_EXTENDED = ?,
                NER = ?,
                NER_EXTENDED = ?,
                MODIFIED_BY = ?,
                DATE_MODIFIED = ?
            WHERE FORECAST_TIERS_KEY = ?
        """, (tier_order, lease_count, rate, rate_extended,
              concession, concession_monthly, concession_extended,
              ner, ner_extended, user_email,
              int(datetime.date.today().strftime("%Y%m%d")),
              tier_key))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


# ─── API: ADD FORECAST TIER ────────────────────────────────────────────────────

@rfs_bp.route("/api/forecast-tiers/add", methods=["POST"])
@login_required
def add_forecast_tier():
    """Add a new forecast tier row."""
    check = _require_access()
    if check:
        return check

    data = request.get_json()
    required = ["forecast_key", "floorplan_key", "floorplan_code",
                "property_key", "property_name", "lease_type"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"{field} required"}), 400

    user_email = _get_user_email()
    today_int = int(datetime.date.today().strftime("%Y%m%d"))
    seed_rate = float(data.get("rate", 0))

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        # Auto-compute next TIER_ORDER
        cur = conn.execute(
            "SELECT ISNULL(MAX(TIER_ORDER), 0) FROM dbo.FORECAST_FORECAST_TIERS "
            "WHERE FORECAST_KEY=? AND FLOORPLAN_KEY=? AND LEASE_TYPE=?",
            [int(data["forecast_key"]), int(data["floorplan_key"]), data["lease_type"]]
        )
        next_order = (cur.fetchone()[0] or 0) + 1

        conn.execute("""
            INSERT INTO dbo.FORECAST_FORECAST_TIERS
                (FORECAST_KEY, FLOORPLAN_KEY, FLOORPLAN_CODE, PROPERTY_KEY,
                 PROPERTY_NAME, LEASE_TYPE, TIER_ORDER, LEASE_COUNT, RATE,
                 RATE_EXTENDED, CONCESSION_AMOUNT, CONCESSION_MONTHLY,
                 CONCESSION_AMOUNT_EXTENDED, NER, NER_EXTENDED,
                 CREATED_BY, MODIFIED_BY, DATE_CREATED, DATE_MODIFIED)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, 0, 0, 0, 0, ?, 0, ?, ?, ?, ?)
        """, (int(data["forecast_key"]), int(data["floorplan_key"]),
              data["floorplan_code"], int(data["property_key"]),
              data["property_name"], data["lease_type"],
              next_order, seed_rate, seed_rate,
              user_email, user_email, today_int, today_int))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


# ─── API: DELETE FORECAST TIER ──────────────────────────────────────────────────

@rfs_bp.route("/api/forecast-tiers/delete", methods=["POST"])
@login_required
def delete_forecast_tier():
    """Delete a forecast tier row."""
    check = _require_access()
    if check:
        return check

    data = request.get_json()
    tier_key = data.get("forecast_tiers_key")
    if not tier_key:
        return jsonify({"error": "forecast_tiers_key required"}), 400

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        cur = conn.execute("""
            DELETE FROM dbo.FORECAST_FORECAST_TIERS
            WHERE FORECAST_TIERS_KEY = ?
        """, (int(tier_key),))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


# ─── API: ACTUALS (RENT + NER) ──────────────────────────────────────────────────

@rfs_bp.route("/api/actuals")
@login_required
def get_actuals():
    """Return actual rent and NER data for a property/floorplan/AY/lease_type."""
    check = _require_access()
    if check:
        return check

    property_key = request.args.get("property_key", type=int)
    floorplan_key = request.args.get("floorplan_key", type=int)
    ay = request.args.get("ay", type=int)
    lease_type = request.args.get("lease_type", "RENEWAL")

    if not all([property_key, floorplan_key, ay]):
        return jsonify({"error": "property_key, floorplan_key, ay required"}), 400

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        # Rent actuals
        cur = conn.execute("""
            SELECT FLOORPLAN_CODE, RENT_PER_SPACE, RENT_PER_SPACE_EXTENDED,
                   LEASED_COUNT_RENT, INTERVAL_TYPE_CONFORMED, ROW_NUMBER
            FROM dbo.FLOORPLAN_ACTUALS_RENT
            WHERE PROPERTY_KEY = ? AND FLOORPLAN_KEY = ?
              AND AY = ? AND INTERVAL_TYPE_CONFORMED = ?
            ORDER BY RENT_PER_SPACE
        """, (property_key, floorplan_key, ay, lease_type))
        cols = [d[0] for d in cur.description]
        rent_rows = [_clean_row(dict(zip(cols, r))) for r in cur.fetchall()]

        # NER actuals
        cur = conn.execute("""
            SELECT FLOORPLAN_CODE, RENT_PER_SPACE, NER_PER_SPACE,
                   NER_PER_SPACE_EXTENDED, LEASED_COUNT_NER,
                   CONCESSION_TOTAL_PER_SPACE_EXTENDED,
                   GIFT_CARD_AMOUNT_PER_SPACE_EXTENDED,
                   INDUCEMENT_TOTAL_PER_SPACE_EXTENDED,
                   INTERVAL_TYPE_CONFORMED, ROW_NUMBER
            FROM dbo.FLOORPLAN_ACTUALS_NER
            WHERE PROPERTY_KEY = ? AND FLOORPLAN_KEY = ?
              AND AY = ? AND INTERVAL_TYPE_CONFORMED = ?
            ORDER BY RENT_PER_SPACE
        """, (property_key, floorplan_key, ay, lease_type))
        cols2 = [d[0] for d in cur.description]
        ner_rows = [_clean_row(dict(zip(cols2, r))) for r in cur.fetchall()]
    finally:
        conn.close()

    return jsonify({"rent": rent_rows, "ner": ner_rows})


# ─── API: PROPERTY SUMMARY (budget inducements, totals) ────────────────────────

@rfs_bp.route("/api/property-summary")
@login_required
def get_property_summary():
    """Return property-level summary: budget inducements, actual inducements, totals."""
    check = _require_access()
    if check:
        return check

    property_key = request.args.get("property_key", type=int)
    floorplan_key = request.args.get("floorplan_key", type=int)
    ay = request.args.get("ay", type=int)
    forecast_key = request.args.get("forecast_key", type=int)

    if not all([property_key, floorplan_key, ay]):
        return jsonify({"error": "property_key, floorplan_key, ay required"}), 400

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:

        # Budget inducements — property-level only (no FLOORPLAN_KEY in this table)
        cur = conn.execute("""
            SELECT ISNULL(SUM(CONCESSION_AGG), 0) AS concession_budget,
                   ISNULL(SUM(GIFT_CARD_AGG), 0) AS gift_card_budget,
                   ISNULL(SUM(INDUCEMENT_AGG), 0) AS inducement_budget
            FROM dbo.FORECAST_BUDGET_INDUCEMENTS
            WHERE PROPERTY_KEY = ? AND AY = ?
        """, (property_key, ay))
        budget_row = cur.fetchone()
        budget = {
            "concession_budget": float(budget_row[0]) if budget_row else 0,
            "gift_card_budget": float(budget_row[1]) if budget_row else 0,
            "inducement_budget": float(budget_row[2]) if budget_row else 0,
        }

        # Actual inducements (from NER actuals) — floorplan-scoped
        cur = conn.execute("""
            SELECT ISNULL(SUM(CONCESSION_TOTAL_PER_SPACE_EXTENDED), 0) AS concession_used,
                   ISNULL(SUM(GIFT_CARD_AMOUNT_PER_SPACE_EXTENDED), 0) AS gift_card_used,
                   ISNULL(SUM(INDUCEMENT_TOTAL_PER_SPACE_EXTENDED), 0) AS inducement_used
            FROM dbo.FLOORPLAN_ACTUALS_NER
            WHERE PROPERTY_KEY = ? AND FLOORPLAN_KEY = ? AND AY = ?
        """, (property_key, floorplan_key, ay))
        actual_row = cur.fetchone()
        actuals = {
            "concession_used": float(actual_row[0]) if actual_row else 0,
            "gift_card_used": float(actual_row[1]) if actual_row else 0,
            "inducement_used": float(actual_row[2]) if actual_row else 0,
        }

        # Per-lease-type actuals (rent + NER) for dashboard — floorplan-scoped
        def _fetch_actuals_by_type(lt):
            cur2 = conn.execute("""
                SELECT ISNULL(SUM(r.RENT_PER_SPACE_EXTENDED),0), ISNULL(SUM(r.LEASED_COUNT_RENT),0)
                FROM dbo.FLOORPLAN_ACTUALS_RENT r
                WHERE r.PROPERTY_KEY = ? AND r.FLOORPLAN_KEY = ? AND r.AY = ? AND r.INTERVAL_TYPE_CONFORMED = ?
            """, (property_key, floorplan_key, ay, lt))
            rr = cur2.fetchone()
            cur2 = conn.execute("""
                SELECT ISNULL(SUM(n.NER_PER_SPACE_EXTENDED),0), ISNULL(SUM(n.LEASED_COUNT_NER),0)
                FROM dbo.FLOORPLAN_ACTUALS_NER n
                WHERE n.PROPERTY_KEY = ? AND n.FLOORPLAN_KEY = ? AND n.AY = ? AND n.INTERVAL_TYPE_CONFORMED = ?
            """, (property_key, floorplan_key, ay, lt))
            nr = cur2.fetchone()
            rent_ext = float(rr[0]); cnt = int(rr[1])
            ner_ext = float(nr[0]); ner_cnt = int(nr[1])
            return {
                "count": cnt,
                "avg_rate": rent_ext / cnt if cnt > 0 else 0,
                "avg_ner": ner_ext / ner_cnt if ner_cnt > 0 else 0,
                "rent_ext": rent_ext, "ner_ext": ner_ext, "ner_cnt": ner_cnt,
            }
        act_r = _fetch_actuals_by_type("RENEWAL")
        act_n = _fetch_actuals_by_type("NEW")

        # Property-level rent/NER totals (actuals) — all types combined
        rent_row = (act_r["rent_ext"] + act_n["rent_ext"],
                    act_r["count"] + act_n["count"])
        ner_row  = (act_r["ner_ext"] + act_n["ner_ext"],
                    act_r["ner_cnt"] + act_n["ner_cnt"])

        # Per-lease-type budget for dashboard — floorplan-scoped
        def _fetch_budget_by_type(lt):
            cur2 = conn.execute("""
                SELECT ISNULL(SUM(BEDS),0), ISNULL(SUM(RATE_EXTENDED1),0),
                       ISNULL(MAX(PROPERTY_BUDGETED_NER),0)
                FROM dbo.FORECAST_BUDGET_TIERS
                WHERE PROPERTY_KEY = ? AND FLOORPLAN_KEY = ? AND AY = ? AND LEASE_TYPE = ? AND TIER_NUMBER <> 0
            """, (property_key, floorplan_key, ay, lt))
            br = cur2.fetchone()
            beds = int(br[0]); rate_ext = float(br[1]); bner = float(br[2])
            return {
                "count": beds,
                "avg_rate": rate_ext / beds if beds > 0 else 0,
                "avg_ner": bner,
                "rate_ext": rate_ext,
            }
        bud_r = _fetch_budget_by_type("RENEWAL")
        bud_n = _fetch_budget_by_type("NEW")
        # Budget NER = Budget Avg Rate (no concessions in budget tiers)
        bud_r["avg_ner"] = bud_r["avg_rate"]
        bud_n["avg_ner"] = bud_n["avg_rate"]

        # Total beds for prelease calc — use BED_COUNT_COMPILED from PROPERTY_0
        cur = conn.execute("""
            SELECT ISNULL(BED_COUNT_COMPILED, 0) AS total_beds
            FROM dbo.PROPERTY_0
            WHERE PROPERTY_KEY = ?
        """, (property_key,))
        beds_row = cur.fetchone()

        # Budget totals (all types, floorplan-scoped)
        cur = conn.execute("""
            SELECT ISNULL(SUM(RATE_EXTENDED1), 0) AS budget_rate_ext,
                   ISNULL(SUM(BEDS), 0) AS budget_beds,
                   ISNULL(MAX(PROPERTY_BUDGETED_NER), 0) AS budget_ner,
                   ISNULL(MAX(PROPERTY_BUDGETED_OCC_PCT), 0) AS budget_occ
            FROM dbo.FORECAST_BUDGET_TIERS
            WHERE PROPERTY_KEY = ? AND FLOORPLAN_KEY = ? AND AY = ?
        """, (property_key, floorplan_key, ay))
        bprop_row = cur.fetchone()

        # Per-lease-type forecast tiers for dashboard — floorplan-scoped
        def _fetch_forecast_by_type(lt):
            if not forecast_key:
                return {"count": 0, "avg_rate": 0, "avg_ner": 0, "rate_ext": 0, "ner_ext": 0, "concession_ext": 0}
            cur2 = conn.execute("""
                SELECT ISNULL(SUM(LEASE_COUNT),0), ISNULL(SUM(RATE_EXTENDED),0),
                       ISNULL(SUM(NER_EXTENDED),0), ISNULL(SUM(CONCESSION_AMOUNT_EXTENDED),0)
                FROM dbo.FORECAST_FORECAST_TIERS
                WHERE FORECAST_KEY = ? AND PROPERTY_KEY = ? AND FLOORPLAN_KEY = ? AND LEASE_TYPE = ?
            """, (forecast_key, property_key, floorplan_key, lt))
            fr = cur2.fetchone()
            cnt = int(fr[0]); rate_ext = float(fr[1]); ner_ext = float(fr[2]); conc_ext = float(fr[3])
            return {
                "count": cnt,
                "avg_rate": rate_ext / cnt if cnt > 0 else 0,
                "avg_ner": ner_ext / cnt if cnt > 0 else 0,
                "rate_ext": rate_ext, "ner_ext": ner_ext, "concession_ext": conc_ext,
            }
        fc_r = _fetch_forecast_by_type("RENEWAL")
        fc_n = _fetch_forecast_by_type("NEW")

        # ── Property-wide queries (for Property panel — all floorplans) ──
        cur = conn.execute("""
            SELECT ISNULL(SUM(RATE_EXTENDED1), 0), ISNULL(SUM(BEDS), 0),
                   ISNULL(MAX(PROPERTY_BUDGETED_NER), 0), ISNULL(MAX(PROPERTY_BUDGETED_OCC_PCT), 0)
            FROM dbo.FORECAST_BUDGET_TIERS
            WHERE PROPERTY_KEY = ? AND AY = ?
        """, (property_key, ay))
        bprop_all = cur.fetchone()

        cur = conn.execute("""
            SELECT ISNULL(SUM(RENT_PER_SPACE_EXTENDED), 0), ISNULL(SUM(LEASED_COUNT_RENT), 0)
            FROM dbo.FLOORPLAN_ACTUALS_RENT
            WHERE PROPERTY_KEY = ? AND AY = ?
        """, (property_key, ay))
        act_all_rent = cur.fetchone()

        cur = conn.execute("""
            SELECT ISNULL(SUM(NER_PER_SPACE_EXTENDED), 0), ISNULL(SUM(LEASED_COUNT_NER), 0)
            FROM dbo.FLOORPLAN_ACTUALS_NER
            WHERE PROPERTY_KEY = ? AND AY = ?
        """, (property_key, ay))
        act_all_ner = cur.fetchone()

        fc_all_row = (0, 0.0, 0.0)
        if forecast_key:
            cur = conn.execute("""
                SELECT ISNULL(SUM(LEASE_COUNT), 0), ISNULL(SUM(RATE_EXTENDED), 0),
                       ISNULL(SUM(NER_EXTENDED), 0)
                FROM dbo.FORECAST_FORECAST_TIERS
                WHERE FORECAST_KEY = ? AND PROPERTY_KEY = ?
            """, (forecast_key, property_key))
            fc_all_row = cur.fetchone()

    finally:
        conn.close()

    total_beds = int(beds_row[0]) if beds_row else 0

    # ── Property-wide metrics for Property panel ──
    pw_bud_rate_ext = float(bprop_all[0]) if bprop_all else 0
    pw_bud_beds = int(bprop_all[1]) if bprop_all else 0
    budget_ner = float(bprop_all[2]) if bprop_all else 0
    budget_occ = float(bprop_all[3]) if bprop_all else 0
    budget_avg_rate = pw_bud_rate_ext / pw_bud_beds if pw_bud_beds > 0 else 0

    pw_act_rent_ext = float(act_all_rent[0]); pw_act_lease_cnt = int(act_all_rent[1])
    pw_act_ner_ext  = float(act_all_ner[0]);  pw_act_ner_cnt   = int(act_all_ner[1])
    actual_avg_rate = pw_act_rent_ext / pw_act_lease_cnt if pw_act_lease_cnt > 0 else 0
    actual_ner      = pw_act_ner_ext  / pw_act_ner_cnt  if pw_act_ner_cnt  > 0 else 0
    actual_prelease = (pw_act_lease_cnt / total_beds * 100) if total_beds > 0 else 0

    pw_fc_cnt = int(fc_all_row[0]); pw_fc_rate_ext = float(fc_all_row[1]); pw_fc_ner_ext = float(fc_all_row[2])
    pw_fc_total = pw_act_lease_cnt + pw_fc_cnt
    fc_avg_rate = (pw_act_rent_ext + pw_fc_rate_ext) / pw_fc_total if pw_fc_total > 0 else 0
    fc_ner      = (pw_act_ner_ext  + pw_fc_ner_ext)  / pw_fc_total if pw_fc_total > 0 else 0
    fc_prelease = (pw_fc_total / total_beds * 100) if total_beds > 0 else 0

    # ── Floorplan-scoped (for dashboard breakdowns) ──
    actual_lease_count = act_r["count"] + act_n["count"]
    actual_rent_ext = act_r["rent_ext"] + act_n["rent_ext"]
    actual_ner_ext = act_r["ner_ext"] + act_n["ner_ext"]
    actual_ner_cnt = act_r["ner_cnt"] + act_n["ner_cnt"]

    # Combined forecast (floorplan-scoped, for dashboard)
    forecast_count = fc_r["count"] + fc_n["count"]
    forecast_rate_ext = fc_r["rate_ext"] + fc_n["rate_ext"]
    forecast_ner_ext = fc_r["ner_ext"] + fc_n["ner_ext"]
    forecast_concession_ext = fc_r["concession_ext"] + fc_n["concession_ext"]

    # Per-lease-type forecasted (actuals + forecast tiers)
    def _fc_combined(act, fc):
        tot_cnt = act["count"] + fc["count"]
        tot_rate = act["rent_ext"] + fc["rate_ext"]
        tot_ner = act["ner_ext"] + fc["ner_ext"]
        return {
            "count": tot_cnt,
            "avg_rate": tot_rate / tot_cnt if tot_cnt > 0 else 0,
            "avg_ner": tot_ner / tot_cnt if tot_cnt > 0 else 0,
            "rate_ext": tot_rate,
            "ner_ext": tot_ner,
        }
    fcd_r = _fc_combined(act_r, fc_r)
    fcd_n = _fc_combined(act_n, fc_n)

    # Total budget NER: weighted average of R+N budget NER by bed count
    bud_total_cnt = bud_r["count"] + bud_n["count"]
    bud_total_avg_rate = (bud_r["rate_ext"] + bud_n["rate_ext"]) / bud_total_cnt if bud_total_cnt > 0 else 0
    # For total budget NER, use MAX(PROPERTY_BUDGETED_NER) from all tiers
    bud_total_ner = budget_ner

    return jsonify({
        **budget,
        **actuals,
        "actual_avg_rate": actual_avg_rate,
        "actual_ner": actual_ner,
        "actual_prelease": actual_prelease,
        "budget_avg_rate": budget_avg_rate,
        "budget_ner": budget_ner,
        "budget_occ": budget_occ,
        "forecast_avg_rate": fc_avg_rate,
        "forecast_ner": fc_ner,
        "forecast_prelease": fc_prelease,
        "forecast_concession_ext": forecast_concession_ext,
        "forecast_count": forecast_count,
        "forecast_rate_ext": forecast_rate_ext,
        "forecast_ner_ext": forecast_ner_ext,
        "total_beds": total_beds,
        # Per-lease-type for dashboard
        "bud_r": bud_r, "bud_n": bud_n,
        "act_r": act_r, "act_n": act_n,
        "fc_r": fc_r, "fc_n": fc_n,
        "fcd_r": fcd_r, "fcd_n": fcd_n,
        "bud_total_cnt": bud_total_cnt,
        "bud_total_avg_rate": bud_total_avg_rate,
        "bud_total_ner": bud_total_ner,
    })


# ─── API: APPROVE FORECAST ─────────────────────────────────────────────────────

@rfs_bp.route("/api/forecasts/approve", methods=["POST"])
@login_required
def approve_forecast():
    """Toggle the FLAG_APPROVED on a forecast."""
    check = _require_access()
    if check:
        return check

    data = request.get_json()
    forecast_key = data.get("forecast_key")
    approved = data.get("approved", False)
    if not forecast_key:
        return jsonify({"error": "forecast_key required"}), 400

    today_int = int(datetime.date.today().strftime("%Y%m%d"))
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        cur = conn.execute("""
            UPDATE dbo.FORECAST_FORECASTS
            SET FLAG_APPROVED = ?, DATE_MODIFIED = ?
            WHERE FORECAST_KEY = ?
        """, (1 if approved else 0, today_int, int(forecast_key)))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


# ─── API: UPDATE PLANNED USE ───────────────────────────────────────────────────

@rfs_bp.route("/api/forecasts/planned-use", methods=["POST"])
@login_required
def update_planned_use():
    """Update the INDUCEMENT_PLANNED_USE on a forecast."""
    check = _require_access()
    if check:
        return check

    data = request.get_json()
    forecast_key = data.get("forecast_key")
    planned_use = data.get("planned_use", 0)
    if not forecast_key:
        return jsonify({"error": "forecast_key required"}), 400

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        cur = conn.execute("""
            UPDATE dbo.FORECAST_FORECASTS
            SET INDUCEMENT_PLANNED_USE = ?
            WHERE FORECAST_KEY = ?
        """, (float(planned_use), int(forecast_key)))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


# ─── API: CREATE NEW FORECAST ──────────────────────────────────────────────────

@rfs_bp.route("/api/forecasts/create", methods=["POST"])
@login_required
def create_forecast():
    """Create a new forecast plan for a property."""
    check = _require_access()
    if check:
        return check

    data = request.get_json()
    property_key = data.get("property_key")
    property_name = data.get("property_name", "")
    forecast_name = data.get("forecast_name", "")
    ay = data.get("ay", 2026)

    if not property_key or not forecast_name:
        return jsonify({"error": "property_key and forecast_name required"}), 400

    user_email = _get_user_email()
    today_int = int(datetime.date.today().strftime("%Y%m%d"))

    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        # Get next FORECAST_KEY
        cur = conn.execute("SELECT ISNULL(MAX(FORECAST_KEY), 0) + 1 FROM dbo.FORECAST_FORECASTS")
        new_key = cur.fetchone()[0]

        cur = conn.execute("""
            INSERT INTO dbo.FORECAST_FORECASTS
                (FORECAST_KEY, AY, FORECAST_NAME, PROPERTY_KEY, PROPERTY_NAME,
                 FLAG_APPROVED, FLAG_ACTIVE, CREATED_BY, MODIFIED_BY,
                 DATE_CREATED, DATE_MODIFIED)
            VALUES (?, ?, ?, ?, ?, 0, 1, ?, ?, ?, ?)
        """, (int(new_key), int(ay), forecast_name, int(property_key),
              property_name, user_email, user_email, today_int, today_int))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, "forecast_key": int(new_key)})
