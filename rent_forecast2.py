"""Rent Forecasting 2.0 — AppHub 4.0 module (Blueprint)."""
import os
import datetime
from decimal import Decimal
from flask import Blueprint, render_template, session, jsonify, request
from auth import login_required
from modules import MODULES, APP_ID_MAP
import sys

sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

rfs2_bp = Blueprint("rfs2", __name__, url_prefix="/rfs2")

_env = None
_APP_ID = 35          # DB-assigned App_ID for Rent Forecasting 2.0
_CURRENT_AY = 2026


def _clean(row):
    """Convert Decimal/date to JSON-safe types."""
    return {k: (float(v) if isinstance(v, Decimal) else v) for k, v in row.items()}


def _get_env():
    global _env
    if _env is None:
        _env = load_env()
    return _env


def _require_access():
    if os.environ.get("DEV_BYPASS", "").lower() == "true":
        return None
    if session.get("is_developer"):
        return None
    for m in session.get("user_modules", []):
        if m["id"] == _APP_ID:
            return None
    return jsonify({"error": "unauthorized"}), 403


def _user_email():
    return (session.get("user") or {}).get("email", "").lower()


def _today_int():
    return int(datetime.date.today().strftime("%Y%m%d"))


# ─── PAGE ROUTE ──────────────────────────────────────────────────────────────

@rfs2_bp.route("/")
@login_required
def index():
    check = _require_access()
    if check:
        return check
    from config import APP_VERSION
    is_dev = session.get("is_developer", False)
    user_modules = session.get("user_modules", [])
    if is_dev or not user_modules:
        visible = MODULES
    else:
        allowed = {APP_ID_MAP[m["id"]] for m in user_modules if m["id"] in APP_ID_MAP}
        visible = [m for m in MODULES if m["id"] in allowed]
    return render_template(
        "rent_forecast2.html",
        modules=visible,
        active_module="rent_forecasting_2",
        user=session.get("user", {}),
        is_developer=session.get("is_developer", False),
        is_dev_mode=session.get("is_dev_mode", False),
        is_impersonating=session.get("is_impersonating", False),
        impersonating_user=session.get("impersonating_user", None),
        version=APP_VERSION,
        current_ay=_CURRENT_AY,
        ay_options=[_CURRENT_AY - 1, _CURRENT_AY, _CURRENT_AY + 1],
    )


# ─── PROPERTIES ──────────────────────────────────────────────────────────────

@rfs2_bp.route("/api/properties")
@login_required
def get_properties():
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
        rows = [_clean(dict(zip(cols, r))) for r in cur.fetchall()]
    finally:
        conn.close()
    user_email = _user_email()
    sec = session.get("security_level", 0)
    if sec == 50:
        rows = [r for r in rows if (r.get("PM_EMAIL") or "").lower() == user_email]
    return jsonify(rows)


# ─── FORECASTS (PLAN DROPDOWN) ────────────────────────────────────────────────

@rfs2_bp.route("/api/forecasts")
@login_required
def get_forecasts():
    check = _require_access()
    if check:
        return check
    prop = request.args.get("property_key", type=int)
    ay   = request.args.get("ay", type=int)
    if not prop:
        return jsonify({"error": "property_key required"}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        sql = """
            SELECT FORECAST_KEY, FORECAST_NAME, AY, PROPERTY_KEY, PROPERTY_NAME,
                   FLAG_APPROVED, FLAG_ARCHIVED, INDUCEMENT_PLANNED_USE,
                   DATE_CREATED, DATE_MODIFIED
            FROM dbo.FORECAST_FORECASTS
            WHERE PROPERTY_KEY = ?
        """
        params = [prop]
        if ay:
            sql += " AND AY = ?"
            params.append(ay)
        sql += " ORDER BY FLAG_ARCHIVED, AY DESC, FORECAST_NAME"
        cur = conn.execute(sql, params)
        cols = [d[0] for d in cur.description]
        rows = [_clean(dict(zip(cols, r))) for r in cur.fetchall()]
    finally:
        conn.close()
    return jsonify(rows)


# ─── FLOORPLANS ───────────────────────────────────────────────────────────────

@rfs2_bp.route("/api/floorplans")
@login_required
def get_floorplans():
    check = _require_access()
    if check:
        return check
    prop = request.args.get("property_key", type=int)
    if not prop:
        return jsonify({"error": "property_key required"}), 400
    env = _get_env()
    conn = SafeConnection(env, "WH_STAGING", None, direct=True)
    try:
        cur = conn.execute("""
            SELECT FLOORPLAN_KEY, FLOORPLAN, FLOORPLAN_CODE,
                   BEDS, COMPARE_AS_FLOORPLAN_TYPE
            FROM dbo.FLOORPLANS_F
            WHERE PROPERTY_KEY = ? AND FLAG_REPORTABLE = 1
              AND FLOORPLAN <> 'DELETED TYPE'
            ORDER BY FLOORPLAN
        """, (prop,))
        cols = [d[0] for d in cur.description]
        rows = [_clean(dict(zip(cols, r))) for r in cur.fetchall()]
    finally:
        conn.close()
    return jsonify(rows)


# ─── BUDGET TIERS ─────────────────────────────────────────────────────────────

@rfs2_bp.route("/api/budget-tiers")
@login_required
def get_budget_tiers():
    check = _require_access()
    if check:
        return check
    prop  = request.args.get("property_key", type=int)
    fp    = request.args.get("floorplan_key", type=int)
    ay    = request.args.get("ay", type=int)
    lt    = request.args.get("lease_type", "RENEWAL")
    if not all([prop, fp, ay]):
        return jsonify({"error": "property_key, floorplan_key, ay required"}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        cur = conn.execute("""
            SELECT TIER_NUMBER, BEDS, RATE, RATE_EXTENDED1, LEASE_TYPE
            FROM dbo.FORECAST_BUDGET_TIERS
            WHERE PROPERTY_KEY=? AND FLOORPLAN_KEY=? AND AY=?
              AND LEASE_TYPE=? AND TIER_NUMBER<>0
            ORDER BY TIER_NUMBER
        """, (prop, fp, ay, lt))
        cols = [d[0] for d in cur.description]
        rows = [_clean(dict(zip(cols, r))) for r in cur.fetchall()]
    finally:
        conn.close()
    return jsonify(rows)


# ─── ACTUALS ──────────────────────────────────────────────────────────────────

@rfs2_bp.route("/api/actuals")
@login_required
def get_actuals():
    check = _require_access()
    if check:
        return check
    prop = request.args.get("property_key", type=int)
    fp   = request.args.get("floorplan_key", type=int)
    ay   = request.args.get("ay", type=int)
    lt   = request.args.get("lease_type", "RENEWAL")
    if not all([prop, fp, ay]):
        return jsonify({"error": "property_key, floorplan_key, ay required"}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        cur = conn.execute("""
            SELECT FLOORPLAN_CODE, RENT_PER_SPACE, RENT_PER_SPACE_EXTENDED,
                   LEASED_COUNT_RENT, INTERVAL_TYPE_CONFORMED, ROW_NUMBER
            FROM dbo.FLOORPLAN_ACTUALS_RENT
            WHERE PROPERTY_KEY=? AND FLOORPLAN_KEY=? AND AY=?
              AND INTERVAL_TYPE_CONFORMED=?
            ORDER BY RENT_PER_SPACE
        """, (prop, fp, ay, lt))
        c = [d[0] for d in cur.description]
        rent = [_clean(dict(zip(c, r))) for r in cur.fetchall()]

        cur = conn.execute("""
            SELECT FLOORPLAN_CODE, RENT_PER_SPACE, NER_PER_SPACE,
                   NER_PER_SPACE_EXTENDED, LEASED_COUNT_NER,
                   CONCESSION_TOTAL_PER_SPACE_EXTENDED,
                   GIFT_CARD_AMOUNT_PER_SPACE_EXTENDED,
                   INDUCEMENT_TOTAL_PER_SPACE_EXTENDED,
                   INTERVAL_TYPE_CONFORMED, ROW_NUMBER
            FROM dbo.FLOORPLAN_ACTUALS_NER
            WHERE PROPERTY_KEY=? AND FLOORPLAN_KEY=? AND AY=?
              AND INTERVAL_TYPE_CONFORMED=?
            ORDER BY RENT_PER_SPACE
        """, (prop, fp, ay, lt))
        c2 = [d[0] for d in cur.description]
        ner = [_clean(dict(zip(c2, r))) for r in cur.fetchall()]
    finally:
        conn.close()
    return jsonify({"rent": rent, "ner": ner})


# ─── FORECAST TIERS ───────────────────────────────────────────────────────────

@rfs2_bp.route("/api/forecast-tiers")
@login_required
def get_forecast_tiers():
    check = _require_access()
    if check:
        return check
    fk = request.args.get("forecast_key", type=int)
    fp = request.args.get("floorplan_key", type=int)
    lt = request.args.get("lease_type", "RENEWAL")
    if not all([fk, fp]):
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
            WHERE FORECAST_KEY=? AND FLOORPLAN_KEY=? AND LEASE_TYPE=?
            ORDER BY TIER_ORDER
        """, (fk, fp, lt))
        cols = [d[0] for d in cur.description]
        rows = [_clean(dict(zip(cols, r))) for r in cur.fetchall()]
    finally:
        conn.close()
    return jsonify(rows)


@rfs2_bp.route("/api/forecast-tiers/save", methods=["POST"])
@login_required
def save_forecast_tier():
    check = _require_access()
    if check:
        return check
    data = request.get_json() or {}
    tk = data.get("forecast_tiers_key")
    if not tk:
        return jsonify({"error": "forecast_tiers_key required"}), 400
    tier_order   = int(data.get("tier_order", 999))
    lease_count  = int(data.get("lease_count", 0))
    rate         = float(data.get("rate", 0))
    concession   = float(data.get("concession_amount", 0))
    rate_ext     = rate * lease_count
    conc_monthly = round(concession / 12, 2) if concession else 0
    conc_ext     = concession * lease_count
    ner          = round(rate - conc_monthly, 2)
    ner_ext      = round(ner * lease_count, 2)
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute("""
            UPDATE dbo.FORECAST_FORECAST_TIERS
            SET TIER_ORDER=?, LEASE_COUNT=?, RATE=?, RATE_EXTENDED=?,
                CONCESSION_AMOUNT=?, CONCESSION_MONTHLY=?, CONCESSION_AMOUNT_EXTENDED=?,
                NER=?, NER_EXTENDED=?, MODIFIED_BY=?, DATE_MODIFIED=?
            WHERE FORECAST_TIERS_KEY=?
        """, (tier_order, lease_count, rate, rate_ext, concession, conc_monthly,
              conc_ext, ner, ner_ext, _user_email(), _today_int(), int(tk)))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, "ner": ner, "ner_ext": ner_ext,
                    "rate_ext": rate_ext, "conc_monthly": conc_monthly})


@rfs2_bp.route("/api/forecast-tiers/add", methods=["POST"])
@login_required
def add_forecast_tier():
    check = _require_access()
    if check:
        return check
    data = request.get_json() or {}
    for f in ["forecast_key", "floorplan_key", "floorplan_code",
              "property_key", "property_name", "lease_type"]:
        if not data.get(f):
            return jsonify({"error": f"{f} required"}), 400
    email = _user_email()
    today = _today_int()
    seed  = float(data.get("rate", 0))
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        cur = conn.execute(
            "SELECT ISNULL(MAX(TIER_ORDER),0) FROM dbo.FORECAST_FORECAST_TIERS "
            "WHERE FORECAST_KEY=? AND FLOORPLAN_KEY=? AND LEASE_TYPE=?",
            [int(data["forecast_key"]), int(data["floorplan_key"]), data["lease_type"]]
        )
        next_ord = (cur.fetchone()[0] or 0) + 1
        cur = conn.execute("""
            INSERT INTO dbo.FORECAST_FORECAST_TIERS
                (FORECAST_KEY, FLOORPLAN_KEY, FLOORPLAN_CODE, PROPERTY_KEY,
                 PROPERTY_NAME, LEASE_TYPE, TIER_ORDER, LEASE_COUNT, RATE,
                 RATE_EXTENDED, CONCESSION_AMOUNT, CONCESSION_MONTHLY,
                 CONCESSION_AMOUNT_EXTENDED, NER, NER_EXTENDED,
                 CREATED_BY, MODIFIED_BY, DATE_CREATED, DATE_MODIFIED)
            OUTPUT INSERTED.FORECAST_TIERS_KEY
            VALUES (?,?,?,?,?,?,?,0,?,0,0,0,0,?,0,?,?,?,?)
        """, (int(data["forecast_key"]), int(data["floorplan_key"]),
              data["floorplan_code"], int(data["property_key"]),
              data["property_name"], data["lease_type"],
              next_ord, seed, seed, email, email, today, today))
        new_key = cur.fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, "forecast_tiers_key": int(new_key), "tier_order": next_ord})


@rfs2_bp.route("/api/forecast-tiers/delete", methods=["POST"])
@login_required
def delete_forecast_tier():
    check = _require_access()
    if check:
        return check
    data = request.get_json() or {}
    tk = data.get("forecast_tiers_key")
    if not tk:
        return jsonify({"error": "forecast_tiers_key required"}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute("DELETE FROM dbo.FORECAST_FORECAST_TIERS WHERE FORECAST_TIERS_KEY=?",
                     (int(tk),))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


# ─── COMPS ────────────────────────────────────────────────────────────────────

@rfs2_bp.route("/api/comps")
@login_required
def get_comps():
    check = _require_access()
    if check:
        return check
    fk   = request.args.get("forecast_key", type=int)
    prop = request.args.get("property_key", type=int)
    ct   = request.args.get("compare_type", "")
    if not all([fk, prop]):
        return jsonify({"error": "forecast_key and property_key required"}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        sql = """
            SELECT FLOORPLAN_ASSIGNMENT_KEY, COMP_PROPERTY_NAME, FLOORPLAN_NAME,
                   COMPARE_AS_FLOORPLAN_TYPE,
                   ISNULL(NER_PRELEASE_FURNISHED, 0) AS NER,
                   FLAG_SOLD_OUT, FLAG_INCLUDE
            FROM dbo.FORECAST_COMP_FLOORPLANS
            WHERE FORECAST_KEY=? AND PARENT_PROPERTY_KEY=?
              AND COMP_PROPERTY_KEY<>PARENT_PROPERTY_KEY
        """
        params = [fk, prop]
        if ct:
            sql += " AND COMPARE_AS_FLOORPLAN_TYPE=?"
            params.append(ct)
        sql += " ORDER BY FLAG_INCLUDE DESC, COMP_PROPERTY_NAME, FLOORPLAN_NAME"
        cur = conn.execute(sql, params)
        cols = [d[0] for d in cur.description]
        rows = [_clean(dict(zip(cols, r))) for r in cur.fetchall()]
    finally:
        conn.close()
    return jsonify(rows)


@rfs2_bp.route("/api/comps/toggle", methods=["POST"])
@login_required
def toggle_comp():
    check = _require_access()
    if check:
        return check
    data = request.get_json() or {}
    fak = data.get("floorplan_assignment_key")
    fk  = data.get("forecast_key")
    if not fak or not fk:
        return jsonify({"error": "floorplan_assignment_key and forecast_key required"}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute(
            "UPDATE dbo.FORECAST_COMP_FLOORPLANS SET FLAG_INCLUDE=1-FLAG_INCLUDE "
            "WHERE FLOORPLAN_ASSIGNMENT_KEY=? AND FORECAST_KEY=?", [fak, fk])
        cur = conn.execute(
            "SELECT FLAG_INCLUDE FROM dbo.FORECAST_COMP_FLOORPLANS "
            "WHERE FLOORPLAN_ASSIGNMENT_KEY=? AND FORECAST_KEY=?", [fak, fk])
        row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()
    return jsonify({"FLAG_INCLUDE": int(row[0]) if row else 0})


# ─── LEFT TO BUDGET ───────────────────────────────────────────────────────────

@rfs2_bp.route("/api/left-to-budget")
@login_required
def get_left_to_budget():
    check = _require_access()
    if check:
        return check
    prop = request.args.get("property_key", type=int)
    fp   = request.args.get("floorplan_key", type=int)
    ay   = request.args.get("ay", type=int)
    fk   = request.args.get("forecast_key", type=int)
    if not all([prop, fp, ay]):
        return jsonify({"error": "property_key, floorplan_key, ay required"}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        bud = conn.execute(
            "SELECT COALESCE(SUM(BEDS),0) FROM dbo.FORECAST_BUDGET_TIERS "
            "WHERE PROPERTY_KEY=? AND FLOORPLAN_KEY=? AND AY=? AND TIER_NUMBER<>0",
            (prop, fp, ay)).fetchone()[0]
        act = conn.execute(
            "SELECT COALESCE(SUM(LEASED_COUNT_RENT),0) FROM dbo.FLOORPLAN_ACTUALS_RENT "
            "WHERE PROPERTY_KEY=? AND FLOORPLAN_KEY=? AND AY=?",
            (prop, fp, ay)).fetchone()[0]
        fc = 0
        if fk:
            fc = conn.execute(
                "SELECT COALESCE(SUM(LEASE_COUNT),0) FROM dbo.FORECAST_FORECAST_TIERS "
                "WHERE FORECAST_KEY=? AND FLOORPLAN_KEY=?",
                (fk, fp)).fetchone()[0]
    finally:
        conn.close()
    return jsonify({"budget_total": bud, "actuals_total": act,
                    "forecast_total": fc, "left_to_budget": bud - act - fc})


# ─── PROPERTY SUMMARY ────────────────────────────────────────────────────────

@rfs2_bp.route("/api/property-summary")
@login_required
def get_property_summary():
    check = _require_access()
    if check:
        return check
    prop = request.args.get("property_key", type=int)
    fp   = request.args.get("floorplan_key", type=int)
    ay   = request.args.get("ay", type=int)
    fk   = request.args.get("forecast_key", type=int)
    if not all([prop, fp, ay]):
        return jsonify({"error": "property_key, floorplan_key, ay required"}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        # Budget inducements (property-level)
        br = conn.execute("""
            SELECT ISNULL(SUM(CONCESSION_AGG),0), ISNULL(SUM(GIFT_CARD_AGG),0),
                   ISNULL(SUM(INDUCEMENT_AGG),0)
            FROM dbo.FORECAST_BUDGET_INDUCEMENTS WHERE PROPERTY_KEY=? AND AY=?
        """, (prop, ay)).fetchone()

        # Actual inducements
        ar = conn.execute("""
            SELECT ISNULL(SUM(CONCESSION_TOTAL_PER_SPACE_EXTENDED),0),
                   ISNULL(SUM(GIFT_CARD_AMOUNT_PER_SPACE_EXTENDED),0),
                   ISNULL(SUM(INDUCEMENT_TOTAL_PER_SPACE_EXTENDED),0)
            FROM dbo.FLOORPLAN_ACTUALS_NER WHERE PROPERTY_KEY=? AND FLOORPLAN_KEY=? AND AY=?
        """, (prop, fp, ay)).fetchone()

        # Total beds
        beds_row = conn.execute(
            "SELECT ISNULL(BED_COUNT_COMPILED,0) FROM dbo.PROPERTY_0 WHERE PROPERTY_KEY=?",
            (prop,)).fetchone()
        total_beds = int(beds_row[0]) if beds_row else 0

        # Property-wide budget
        bprop = conn.execute("""
            SELECT ISNULL(SUM(RATE_EXTENDED1),0), ISNULL(SUM(BEDS),0),
                   ISNULL(MAX(PROPERTY_BUDGETED_NER),0), ISNULL(MAX(PROPERTY_BUDGETED_OCC_PCT),0)
            FROM dbo.FORECAST_BUDGET_TIERS WHERE PROPERTY_KEY=? AND AY=?
        """, (prop, ay)).fetchone()

        # Property-wide actuals
        arent = conn.execute("""
            SELECT ISNULL(SUM(RENT_PER_SPACE_EXTENDED),0), ISNULL(SUM(LEASED_COUNT_RENT),0)
            FROM dbo.FLOORPLAN_ACTUALS_RENT WHERE PROPERTY_KEY=? AND AY=?
        """, (prop, ay)).fetchone()
        aner = conn.execute("""
            SELECT ISNULL(SUM(NER_PER_SPACE_EXTENDED),0), ISNULL(SUM(LEASED_COUNT_NER),0)
            FROM dbo.FLOORPLAN_ACTUALS_NER WHERE PROPERTY_KEY=? AND AY=?
        """, (prop, ay)).fetchone()

        # Property-wide forecast tiers
        fc_row = (0, 0.0, 0.0)
        if fk:
            fc_row = conn.execute("""
                SELECT ISNULL(SUM(LEASE_COUNT),0), ISNULL(SUM(RATE_EXTENDED),0),
                       ISNULL(SUM(NER_EXTENDED),0)
                FROM dbo.FORECAST_FORECAST_TIERS WHERE FORECAST_KEY=? AND PROPERTY_KEY=?
            """, (fk, prop)).fetchone()

        def _lt(lease_type):
            rr = conn.execute("""
                SELECT ISNULL(SUM(RENT_PER_SPACE_EXTENDED),0), ISNULL(SUM(LEASED_COUNT_RENT),0)
                FROM dbo.FLOORPLAN_ACTUALS_RENT
                WHERE PROPERTY_KEY=? AND FLOORPLAN_KEY=? AND AY=? AND INTERVAL_TYPE_CONFORMED=?
            """, (prop, fp, ay, lease_type)).fetchone()
            nr = conn.execute("""
                SELECT ISNULL(SUM(NER_PER_SPACE_EXTENDED),0), ISNULL(SUM(LEASED_COUNT_NER),0)
                FROM dbo.FLOORPLAN_ACTUALS_NER
                WHERE PROPERTY_KEY=? AND FLOORPLAN_KEY=? AND AY=? AND INTERVAL_TYPE_CONFORMED=?
            """, (prop, fp, ay, lease_type)).fetchone()
            rc = int(rr[1]); re = float(rr[0])
            nc = int(nr[1]); ne = float(nr[0])
            return {"count": rc, "rent_ext": re, "ner_ext": ne, "ner_cnt": nc,
                    "avg_rate": re/rc if rc else 0, "avg_ner": ne/nc if nc else 0}

        def _blt(lease_type):
            br2 = conn.execute("""
                SELECT ISNULL(SUM(BEDS),0), ISNULL(SUM(RATE_EXTENDED1),0)
                FROM dbo.FORECAST_BUDGET_TIERS
                WHERE PROPERTY_KEY=? AND FLOORPLAN_KEY=? AND AY=? AND LEASE_TYPE=? AND TIER_NUMBER<>0
            """, (prop, fp, ay, lease_type)).fetchone()
            bc = int(br2[0]); be = float(br2[1])
            return {"count": bc, "rate_ext": be, "avg_rate": be/bc if bc else 0,
                    "avg_ner": be/bc if bc else 0}

        def _flt(lease_type):
            if not fk:
                return {"count": 0, "avg_rate": 0, "avg_ner": 0,
                        "rate_ext": 0, "ner_ext": 0, "concession_ext": 0}
            fr = conn.execute("""
                SELECT ISNULL(SUM(LEASE_COUNT),0), ISNULL(SUM(RATE_EXTENDED),0),
                       ISNULL(SUM(NER_EXTENDED),0), ISNULL(SUM(CONCESSION_AMOUNT_EXTENDED),0)
                FROM dbo.FORECAST_FORECAST_TIERS
                WHERE FORECAST_KEY=? AND PROPERTY_KEY=? AND FLOORPLAN_KEY=? AND LEASE_TYPE=?
            """, (fk, prop, fp, lease_type)).fetchone()
            fc2 = int(fr[0]); fe = float(fr[1]); fn = float(fr[2]); fce = float(fr[3])
            return {"count": fc2, "avg_rate": fe/fc2 if fc2 else 0,
                    "avg_ner": fn/fc2 if fc2 else 0, "rate_ext": fe,
                    "ner_ext": fn, "concession_ext": fce}

        act_r = _lt("RENEWAL"); act_n = _lt("NEW")
        bud_r = _blt("RENEWAL"); bud_n = _blt("NEW")
        fc_r  = _flt("RENEWAL"); fc_n  = _flt("NEW")

    finally:
        conn.close()

    # Property-wide calcs
    bud_beds = int(bprop[1]); bud_rate_ext = float(bprop[0])
    budget_ner = float(bprop[2]); budget_occ = float(bprop[3])
    budget_avg_rate = bud_rate_ext / bud_beds if bud_beds else 0

    act_cnt = int(arent[1]); act_rent_ext = float(arent[0])
    act_ner_cnt = int(aner[1]); act_ner_ext = float(aner[0])
    actual_avg_rate = act_rent_ext / act_cnt if act_cnt else 0
    actual_ner      = act_ner_ext / act_ner_cnt if act_ner_cnt else 0
    actual_prelease = act_cnt / total_beds * 100 if total_beds else 0

    fc_cnt = int(fc_row[0]); fc_rent_ext = float(fc_row[1]); fc_ner_ext = float(fc_row[2])
    fc_total = act_cnt + fc_cnt
    fc_avg_rate = (act_rent_ext + fc_rent_ext) / fc_total if fc_total else 0
    fc_ner      = (act_ner_ext  + fc_ner_ext)  / fc_total if fc_total else 0
    fc_prelease = fc_total / total_beds * 100 if total_beds else 0

    def _fcd(act, fc):
        t = act["count"] + fc["count"]
        return {"count": t,
                "avg_rate": (act["rent_ext"] + fc["rate_ext"]) / t if t else 0,
                "avg_ner":  (act["ner_ext"]  + fc["ner_ext"])  / t if t else 0,
                "rate_ext": act["rent_ext"] + fc["rate_ext"],
                "ner_ext":  act["ner_ext"]  + fc["ner_ext"]}

    return jsonify({
        "concession_budget":  float(br[0]), "gift_card_budget": float(br[1]),
        "inducement_budget":  float(br[2]),
        "concession_used":    float(ar[0]), "gift_card_used": float(ar[1]),
        "inducement_used":    float(ar[2]),
        "actual_avg_rate": actual_avg_rate, "actual_ner": actual_ner,
        "actual_prelease": actual_prelease,
        "budget_avg_rate": budget_avg_rate, "budget_ner": budget_ner,
        "budget_occ": budget_occ,
        "forecast_avg_rate": fc_avg_rate, "forecast_ner": fc_ner,
        "forecast_prelease": fc_prelease, "total_beds": total_beds,
        # Revenue vs Budget fields
        "budget_rev":       bud_rate_ext,
        "bud_beds_total":   bud_beds,
        "forecast_rev":     act_rent_ext + fc_rent_ext,
        "fc_beds_total":    fc_total,
        "forecast_ner_rev": act_ner_ext + fc_ner_ext,
        "bud_r": bud_r, "bud_n": bud_n,
        "act_r": act_r, "act_n": act_n,
        "fc_r":  fc_r,  "fc_n":  fc_n,
        "fcd_r": _fcd(act_r, fc_r), "fcd_n": _fcd(act_n, fc_n),
    })


# ─── RATE TRENDS ─────────────────────────────────────────────────────────────

@rfs2_bp.route("/api/rate-trends")
@login_required
def get_rate_trends():
    """NER by tier for the Rate Trends chart: budget / actuals / reforecast."""
    check = _require_access()
    if check:
        return check
    prop = request.args.get("property_key", type=int)
    fp   = request.args.get("floorplan_key", type=int)
    ay   = request.args.get("ay", type=int)
    fk   = request.args.get("forecast_key", type=int)
    if not all([prop, fp, ay]):
        return jsonify({"error": "property_key, floorplan_key, ay required"}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        # Budget tiers — NER = RATE (no concessions in budget)
        cur = conn.execute("""
            SELECT TIER_NUMBER, BEDS, RATE AS NER, LEASE_TYPE
            FROM dbo.FORECAST_BUDGET_TIERS
            WHERE PROPERTY_KEY=? AND FLOORPLAN_KEY=? AND AY=? AND TIER_NUMBER<>0
            ORDER BY LEASE_TYPE, TIER_NUMBER
        """, (prop, fp, ay))
        c = [d[0] for d in cur.description]
        budget = [_clean(dict(zip(c, r))) for r in cur.fetchall()]

        # Actuals — NER from NER actuals table, LEASED_COUNT as bed size
        cur = conn.execute("""
            SELECT ROW_NUMBER AS TIER_ORDER, NER_PER_SPACE AS NER,
                   LEASED_COUNT_NER AS BEDS, INTERVAL_TYPE_CONFORMED AS LEASE_TYPE
            FROM dbo.FLOORPLAN_ACTUALS_NER
            WHERE PROPERTY_KEY=? AND FLOORPLAN_KEY=? AND AY=?
            ORDER BY INTERVAL_TYPE_CONFORMED, NER_PER_SPACE
        """, (prop, fp, ay))
        c2 = [d[0] for d in cur.description]
        actuals = [_clean(dict(zip(c2, r))) for r in cur.fetchall()]

        # Reforecast tiers
        refc = []
        if fk:
            cur = conn.execute("""
                SELECT TIER_ORDER, NER, LEASE_COUNT AS BEDS, LEASE_TYPE
                FROM dbo.FORECAST_FORECAST_TIERS
                WHERE FORECAST_KEY=? AND FLOORPLAN_KEY=?
                ORDER BY LEASE_TYPE, TIER_ORDER
            """, (fk, fp))
            c3 = [d[0] for d in cur.description]
            refc = [_clean(dict(zip(c3, r))) for r in cur.fetchall()]
    finally:
        conn.close()
    return jsonify({"budget": budget, "actuals": actuals, "reforecast": refc})


# ─── LEASING TREND ────────────────────────────────────────────────────────────

@rfs2_bp.route("/api/leasing-trend")
@login_required
def get_leasing_trend():
    """Weekly leases: CY actuals + PY1 actuals (LEASE_AGG) + budget (Adaptive)."""
    check = _require_access()
    if check:
        return check
    prop = request.args.get("property_key", type=int)
    ay   = request.args.get("ay", type=int)
    fp   = request.args.get("floorplan_key", type=int)
    if not all([prop, ay, fp]):
        return jsonify({"error": "property_key, ay, floorplan_key required"}), 400

    import datetime as _dt

    def _first_monday_of_sep(year):
        """Return date of first Monday of September of given year."""
        sep1 = _dt.date(year, 9, 1)
        # weekday(): Mon=0 ... Sun=6
        days_to_mon = (7 - sep1.weekday()) % 7
        return sep1 + _dt.timedelta(days=days_to_mon)

    today    = _dt.date.today()
    cy_w1    = _first_monday_of_sep(ay - 1)      # e.g. Sep 1 2025 for AY2026
    py1_w1   = _first_monday_of_sep(ay - 2)      # e.g. Sep 2 2024 for AY2025

    # Current AY week
    current_week = max(1, min(52, (today - cy_w1).days // 7 + 1)) if today >= cy_w1 else 1
    w_start = max(1, current_week - 7)
    w_end   = min(52, current_week + 2)

    # Date range for CY actuals query
    cy_date_min = cy_w1 + _dt.timedelta(weeks=w_start - 1)
    cy_date_max = cy_w1 + _dt.timedelta(weeks=min(current_week, w_end) - 1, days=6)
    cy_date_min_int = int(cy_date_min.strftime("%Y%m%d"))
    cy_date_max_int = int(cy_date_max.strftime("%Y%m%d"))

    # Date range for PY1 actuals (same relative weeks, prior year)
    py1_date_min = py1_w1 + _dt.timedelta(weeks=w_start - 1)
    py1_date_max = py1_w1 + _dt.timedelta(weeks=w_end - 1, days=6)
    py1_date_min_int = int(py1_date_min.strftime("%Y%m%d"))
    py1_date_max_int = int(py1_date_max.strftime("%Y%m%d"))

    def _week_sql(w1_date_str):
        return f"DATEDIFF(day, '{w1_date_str}', CONVERT(date, CAST(DATE_KEY AS varchar(8)))) / 7 + 1"

    cy_w1_str  = cy_w1.strftime("%Y-%m-%d")
    py1_w1_str = py1_w1.strftime("%Y-%m-%d")

    def _ay_label(y):
        return f"{y-2000}-{y-2000+1} AY"

    def _ay_table(y):
        if y >= 2026:
            return "dbo.Adaptive_Weekly_Tracker_Targets"
        return f"dbo.Adaptive_Weekly_Tracker_Targets_{y}"

    env = _get_env()

    # ── Budget (Adaptive) from DB_APP_SUPPORT ──────────────────────────────────
    app_conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        cy_label  = _ay_label(ay)
        cy_tbl    = _ay_table(ay)

        # Bed share scale factor
        fp_beds = app_conn.execute(
            "SELECT ISNULL(SUM(BEDS),0) FROM dbo.FORECAST_BUDGET_TIERS "
            "WHERE PROPERTY_KEY=? AND FLOORPLAN_KEY=? AND AY=? AND TIER_NUMBER<>0",
            (prop, fp, ay)).fetchone()[0] or 0
        prop_beds = app_conn.execute(
            "SELECT ISNULL(SUM(BEDS),0) FROM dbo.FORECAST_BUDGET_TIERS "
            "WHERE PROPERTY_KEY=? AND AY=? AND TIER_NUMBER<>0",
            (prop, ay)).fetchone()[0] or 1
        scale = float(fp_beds) / float(prop_beds) if prop_beds else 1.0

        budget_sql = f"""
            SELECT CAST(SUBSTRING(t.Week_Beginning, 2, 10) AS INT) AS wk,
                   ISNULL(t.Total_Weekly,  0) AS total,
                   ISNULL(t.New_Weekly,    0) AS new_l,
                   ISNULL(t.Renewal_Weekly,0) AS renewal
            FROM {cy_tbl} t
            JOIN dbo.PROPERTY_0 p
              ON p.PROPERTY_NAME = UPPER(LTRIM(SUBSTRING(
                    t.Levels, CHARINDEX(' ', t.Levels)+1, 200)))
            WHERE t.Academic_Yr = ? AND p.PROPERTY_KEY = ?
              AND CAST(SUBSTRING(t.Week_Beginning, 2, 10) AS INT) BETWEEN ? AND ?
            ORDER BY wk
        """
        cur = app_conn.execute(budget_sql, (cy_label, prop, w_start, w_end))
        budget_raw = cur.fetchall()
        budget_data = [{"week": int(r[0]),
                        "total":   round(float(r[1] or 0) * scale, 2),
                        "new":     round(float(r[2] or 0) * scale, 2),
                        "renewal": round(float(r[3] or 0) * scale, 2)}
                       for r in budget_raw]
    finally:
        app_conn.close()

    # ── Actuals (LEASE_AGG) from WH_PROD2 ────────────────────────────────────
    wh_conn = SafeConnection(env, "WH_PROD2", None)
    try:
        # CY actuals — velocity flags = "this week" completions
        cy_wk_expr = _week_sql(cy_w1_str)
        cur = wh_conn.execute(f"""
            SELECT {cy_wk_expr}            AS ay_week,
                   MAX(FLAG_LEASE_VELOCITY_TOTAL)   AS total,
                   MAX(FLAG_LEASE_VELOCITY_NEW)     AS new_l,
                   MAX(FLAG_LEASE_VELOCITY_RENEWAL) AS renewal
            FROM WH_PROD2.dbo.LEASE_AGG
            WHERE PROPERTY_KEY=? AND FLOORPLAN_KEY=? AND AY=?
              AND DATE_KEY >= ? AND DATE_KEY <= ?
            GROUP BY {cy_wk_expr}
            ORDER BY ay_week
        """, (prop, fp, ay, cy_date_min_int, cy_date_max_int))
        actuals_cy = [{"week": int(r[0]), "total": int(r[1] or 0),
                       "new": int(r[2] or 0), "renewal": int(r[3] or 0)}
                      for r in cur.fetchall()]

        # PY1 actuals — same relative weeks, prior AY
        py1_wk_expr = _week_sql(py1_w1_str)
        cur = wh_conn.execute(f"""
            SELECT {py1_wk_expr}           AS ay_week,
                   MAX(FLAG_LEASE_VELOCITY_TOTAL)   AS total,
                   MAX(FLAG_LEASE_VELOCITY_NEW)     AS new_l,
                   MAX(FLAG_LEASE_VELOCITY_RENEWAL) AS renewal
            FROM WH_PROD2.dbo.LEASE_AGG
            WHERE PROPERTY_KEY=? AND FLOORPLAN_KEY=? AND AY=?
              AND DATE_KEY >= ? AND DATE_KEY <= ?
            GROUP BY {py1_wk_expr}
            ORDER BY ay_week
        """, (prop, fp, ay - 1, py1_date_min_int, py1_date_max_int))
        actuals_py1 = [{"week": int(r[0]), "total": int(r[1] or 0),
                        "new": int(r[2] or 0), "renewal": int(r[3] or 0)}
                       for r in cur.fetchall()]
    finally:
        wh_conn.close()

    return jsonify({
        "budget":      budget_data,
        "actuals_cy":  actuals_cy,
        "actuals_py1": actuals_py1,
        "current_week": current_week,
        "window_start": w_start,
        "window_end":   w_end,
        "cy_label":  _ay_label(ay),
        "py1_label": _ay_label(ay - 1),
        "fp_beds": int(fp_beds), "prop_beds": int(prop_beds),
    })


# ─── FORECAST PLAN CRUD ───────────────────────────────────────────────────────

@rfs2_bp.route("/api/forecasts/approve", methods=["POST"])
@login_required
def approve_forecast():
    check = _require_access()
    if check:
        return check
    data = request.get_json() or {}
    fk = data.get("forecast_key")
    if not fk:
        return jsonify({"error": "forecast_key required"}), 400
    approved = 1 if data.get("approved") else 0
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute(
            "UPDATE dbo.FORECAST_FORECASTS SET FLAG_APPROVED=?, DATE_MODIFIED=? "
            "WHERE FORECAST_KEY=?", (approved, _today_int(), int(fk)))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


@rfs2_bp.route("/api/forecasts/planned-use", methods=["POST"])
@login_required
def update_planned_use():
    check = _require_access()
    if check:
        return check
    data = request.get_json() or {}
    fk = data.get("forecast_key")
    if not fk:
        return jsonify({"error": "forecast_key required"}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute(
            "UPDATE dbo.FORECAST_FORECASTS SET INDUCEMENT_PLANNED_USE=?, DATE_MODIFIED=? "
            "WHERE FORECAST_KEY=?",
            (float(data.get("planned_use", 0)), _today_int(), int(fk)))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


@rfs2_bp.route("/api/forecasts/create", methods=["POST"])
@login_required
def create_forecast():
    check = _require_access()
    if check:
        return check
    data = request.get_json() or {}
    prop      = data.get("property_key")
    prop_name = data.get("property_name", "")
    fc_name   = data.get("forecast_name", "")
    ay        = data.get("ay", _CURRENT_AY)
    if not prop or not fc_name:
        return jsonify({"error": "property_key and forecast_name required"}), 400
    email = _user_email(); today = _today_int()
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        cur = conn.execute("SELECT ISNULL(MAX(FORECAST_KEY),0)+1 FROM dbo.FORECAST_FORECASTS")
        new_key = cur.fetchone()[0]
        conn.execute("""
            INSERT INTO dbo.FORECAST_FORECASTS
                (FORECAST_KEY, AY, FORECAST_NAME, PROPERTY_KEY, PROPERTY_NAME,
                 FLAG_APPROVED, FLAG_ACTIVE, FLAG_ARCHIVED, CREATED_BY, MODIFIED_BY,
                 DATE_CREATED, DATE_MODIFIED)
            VALUES (?,?,?,?,?,0,1,0,?,?,?,?)
        """, (int(new_key), int(ay), fc_name, int(prop), prop_name,
              email, email, today, today))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, "forecast_key": int(new_key)})


@rfs2_bp.route("/api/forecasts/clone", methods=["POST"])
@login_required
def clone_forecast():
    """Clone an existing forecast plan (header + all tiers) with a new name."""
    check = _require_access()
    if check:
        return check
    data = request.get_json() or {}
    src_fk    = data.get("forecast_key")
    new_name  = data.get("new_name", "")
    if not src_fk or not new_name:
        return jsonify({"error": "forecast_key and new_name required"}), 400
    email = _user_email(); today = _today_int()
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        # Get source header
        cur = conn.execute(
            "SELECT AY, PROPERTY_KEY, PROPERTY_NAME, INDUCEMENT_PLANNED_USE "
            "FROM dbo.FORECAST_FORECASTS WHERE FORECAST_KEY=?", (int(src_fk),))
        src = cur.fetchone()
        if not src:
            return jsonify({"error": "source forecast not found"}), 404
        ay, prop_key, prop_name, planned_use = src

        # New key
        cur = conn.execute("SELECT ISNULL(MAX(FORECAST_KEY),0)+1 FROM dbo.FORECAST_FORECASTS")
        new_key = cur.fetchone()[0]

        conn.execute("""
            INSERT INTO dbo.FORECAST_FORECASTS
                (FORECAST_KEY, AY, FORECAST_NAME, PROPERTY_KEY, PROPERTY_NAME,
                 FLAG_APPROVED, FLAG_ACTIVE, FLAG_ARCHIVED, INDUCEMENT_PLANNED_USE,
                 CREATED_BY, MODIFIED_BY, DATE_CREATED, DATE_MODIFIED)
            VALUES (?,?,?,?,?,0,1,0,?,?,?,?,?)
        """, (int(new_key), ay, new_name, prop_key, prop_name,
              planned_use or 0, email, email, today, today))

        # Clone all tier rows (new TIER keys via auto-increment handled by DB)
        cur = conn.execute("""
            SELECT FLOORPLAN_KEY, FLOORPLAN_CODE, PROPERTY_KEY, PROPERTY_NAME,
                   LEASE_TYPE, TIER_ORDER, LEASE_COUNT, RATE, RATE_EXTENDED,
                   CONCESSION_AMOUNT, CONCESSION_MONTHLY, CONCESSION_AMOUNT_EXTENDED,
                   NER, NER_EXTENDED
            FROM dbo.FORECAST_FORECAST_TIERS WHERE FORECAST_KEY=?
        """, (int(src_fk),))
        tier_rows = cur.fetchall()
        for t in tier_rows:
            conn.execute("""
                INSERT INTO dbo.FORECAST_FORECAST_TIERS
                    (FORECAST_KEY, FLOORPLAN_KEY, FLOORPLAN_CODE, PROPERTY_KEY, PROPERTY_NAME,
                     LEASE_TYPE, TIER_ORDER, LEASE_COUNT, RATE, RATE_EXTENDED,
                     CONCESSION_AMOUNT, CONCESSION_MONTHLY, CONCESSION_AMOUNT_EXTENDED,
                     NER, NER_EXTENDED, CREATED_BY, MODIFIED_BY, DATE_CREATED, DATE_MODIFIED)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (int(new_key), t[0], t[1], t[2], t[3], t[4], t[5], t[6], t[7], t[8],
                  t[9], t[10], t[11], t[12], t[13], email, email, today, today))
        # Clone FP inducement rows
        fp_ind_rows = conn.execute(
            "SELECT FLOORPLAN_KEY, PLANNED_USE FROM dbo.FORECAST_FP_INDUCEMENT "
            "WHERE FORECAST_KEY=?", (int(src_fk),)).fetchall()
        for fi in fp_ind_rows:
            conn.execute(
                "INSERT INTO dbo.FORECAST_FP_INDUCEMENT "
                "(FORECAST_KEY, FLOORPLAN_KEY, PLANNED_USE, CREATED_BY, DATE_CREATED, DATE_MODIFIED) "
                "VALUES (?,?,?,?,?,?)",
                (int(new_key), fi[0], fi[1], email, today, today))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, "forecast_key": int(new_key)})


# ─── FP-LEVEL INDUCEMENT (planned use per floorplan) ─────────────────────────

@rfs2_bp.route("/api/fp-inducements", methods=["GET"])
@login_required
def get_all_fp_inducements():
    check = _require_access()
    if check:
        return check
    fk = request.args.get("forecast_key", type=int)
    if not fk:
        return jsonify([])
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        cur = conn.execute(
            "SELECT FLOORPLAN_KEY, PLANNED_USE FROM dbo.FORECAST_FP_INDUCEMENT "
            "WHERE FORECAST_KEY=?",
            (fk,))
        rows = cur.fetchall()
        return jsonify([{"floorplan_key": int(r[0]), "planned_use": float(r[1])} for r in rows])
    finally:
        conn.close()


@rfs2_bp.route("/api/fp-inducement", methods=["GET"])
@login_required
def get_fp_inducement():
    check = _require_access()
    if check:
        return check
    fk = request.args.get("forecast_key", type=int)
    fp = request.args.get("floorplan_key", type=int)
    if not fk or not fp:
        return jsonify({"planned_use": 0})
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        cur = conn.execute(
            "SELECT PLANNED_USE FROM dbo.FORECAST_FP_INDUCEMENT "
            "WHERE FORECAST_KEY=? AND FLOORPLAN_KEY=?",
            (fk, fp))
        row = cur.fetchone()
        return jsonify({"planned_use": float(row[0]) if row else 0})
    finally:
        conn.close()


@rfs2_bp.route("/api/fp-inducement", methods=["POST"])
@login_required
def save_fp_inducement():
    check = _require_access()
    if check:
        return check
    data = request.get_json() or {}
    fk  = data.get("forecast_key")
    fp  = data.get("floorplan_key")
    val = float(data.get("planned_use", 0) or 0)
    if not fk or not fp:
        return jsonify({"error": "forecast_key and floorplan_key required"}), 400
    email = _user_email(); today = _today_int()
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        cur = conn.execute(
            "SELECT FP_INDUCEMENT_KEY FROM dbo.FORECAST_FP_INDUCEMENT "
            "WHERE FORECAST_KEY=? AND FLOORPLAN_KEY=?",
            (int(fk), int(fp)))
        row = cur.fetchone()
        if row:
            conn.execute(
                "UPDATE dbo.FORECAST_FP_INDUCEMENT "
                "SET PLANNED_USE=?, DATE_MODIFIED=? "
                "WHERE FORECAST_KEY=? AND FLOORPLAN_KEY=?",
                (val, today, int(fk), int(fp)))
        else:
            conn.execute(
                "INSERT INTO dbo.FORECAST_FP_INDUCEMENT "
                "(FORECAST_KEY, FLOORPLAN_KEY, PLANNED_USE, CREATED_BY, DATE_CREATED, DATE_MODIFIED) "
                "VALUES (?,?,?,?,?,?)",
                (int(fk), int(fp), val, email, today, today))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})

@login_required
def archive_forecast():
    check = _require_access()
    if check:
        return check
    data = request.get_json() or {}
    fk = data.get("forecast_key")
    if not fk:
        return jsonify({"error": "forecast_key required"}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute(
            "UPDATE dbo.FORECAST_FORECASTS SET FLAG_ARCHIVED=1, DATE_MODIFIED=? "
            "WHERE FORECAST_KEY=?", (_today_int(), int(fk)))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


@rfs2_bp.route("/api/forecasts/revive", methods=["POST"])
@login_required
def revive_forecast():
    check = _require_access()
    if check:
        return check
    data = request.get_json() or {}
    fk = data.get("forecast_key")
    if not fk:
        return jsonify({"error": "forecast_key required"}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute(
            "UPDATE dbo.FORECAST_FORECASTS SET FLAG_ARCHIVED=0, DATE_MODIFIED=? "
            "WHERE FORECAST_KEY=?", (_today_int(), int(fk)))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


# ─── PRE-APPROVAL CHECKS ──────────────────────────────────────────────────────

@rfs2_bp.route("/api/approval-check")
@login_required
def approval_check():
    check = _require_access()
    if check:
        return check
    fk   = request.args.get("forecast_key", type=int)
    prop = request.args.get("property_key", type=int)
    ay   = request.args.get("ay", type=int)
    if not fk or not prop or not ay:
        return jsonify({"error": "forecast_key, property_key, ay required"}), 400

    env  = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    warnings = []
    try:
        total_beds = int((conn.execute(
            "SELECT ISNULL(BED_COUNT_COMPILED,0) FROM dbo.PROPERTY_0 WHERE PROPERTY_KEY=?",
            (prop,)).fetchone() or [0])[0])

        budget_fps = {r[0] for r in conn.execute(
            "SELECT DISTINCT FLOORPLAN_KEY FROM dbo.FORECAST_BUDGET_TIERS "
            "WHERE PROPERTY_KEY=? AND AY=? AND TIER_NUMBER<>0",
            (prop, ay)).fetchall()}

        forecast_fps = {r[0] for r in conn.execute(
            "SELECT DISTINCT FLOORPLAN_KEY FROM dbo.FORECAST_FORECAST_TIERS "
            "WHERE FORECAST_KEY=?", (fk,)).fetchall()}

        missing = budget_fps - forecast_fps
        if missing:
            warnings.append({
                "level": "error",
                "msg": f"{len(missing)} floor plan(s) have budget tiers but no reforecast tiers",
                "fp_keys": list(missing),
            })

        fc_beds = int((conn.execute(
            "SELECT ISNULL(SUM(LEASE_COUNT),0) FROM dbo.FORECAST_FORECAST_TIERS "
            "WHERE FORECAST_KEY=?", (fk,)).fetchone() or [0])[0])

        act_beds = int((conn.execute(
            "SELECT ISNULL(SUM(LEASED_COUNT_RENT),0) FROM dbo.FLOORPLAN_ACTUALS_RENT "
            "WHERE PROPERTY_KEY=? AND AY=?", (prop, ay)).fetchone() or [0])[0])

        total_projected = act_beds + fc_beds

        if total_beds > 0 and total_projected > total_beds:
            warnings.append({
                "level": "error",
                "msg": f"Projected total ({total_projected} beds) exceeds property inventory ({total_beds} beds)",
            })

        bud_beds = int((conn.execute(
            "SELECT ISNULL(SUM(BEDS),0) FROM dbo.FORECAST_BUDGET_TIERS "
            "WHERE PROPERTY_KEY=? AND AY=? AND TIER_NUMBER<>0",
            (prop, ay)).fetchone() or [0])[0])

        if bud_beds > 0 and total_projected < round(bud_beds * 0.85):
            warnings.append({
                "level": "warn",
                "msg": (f"Projected occupancy ({total_projected} beds) is significantly "
                        f"below budget ({bud_beds} beds)"),
            })

        prop_plan = float((conn.execute(
            "SELECT ISNULL(INDUCEMENT_PLANNED_USE,0) FROM dbo.FORECAST_FORECASTS "
            "WHERE FORECAST_KEY=?", (fk,)).fetchone() or [0])[0])

        fp_plan_total = float((conn.execute(
            "SELECT ISNULL(SUM(PLANNED_USE),0) FROM dbo.FORECAST_FP_INDUCEMENT "
            "WHERE FORECAST_KEY=?", (fk,)).fetchone() or [0])[0])

        if prop_plan > 0 and fp_plan_total > prop_plan:
            warnings.append({
                "level": "warn",
                "msg": (f"FP-level planned inducements (${fp_plan_total:,.0f}) "
                        f"exceed property planned total (${prop_plan:,.0f})"),
            })

    finally:
        conn.close()

    has_errors = any(w["level"] == "error" for w in warnings)
    return jsonify({"warnings": warnings, "ok": not has_errors})
