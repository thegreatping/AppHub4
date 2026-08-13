"""SAM Ad Spend Planning module.

Budget planning and YTD tracking for sales/marketing ad spend,
organized by property and GL code hierarchy.

Data source : DB_APP_SUPPORT.dbo.SAM_GL_WORKTABLE  (SQL — always direct=True)
              DB_APP_SUPPORT.dbo.PROPERTY_0         (property lookup)
APP_ID      : 10

Column layout — 12 budget months, 12 new/actual months, 4 quarterly summaries:
  BUD_1..12   budget by month (read-only)
  NEW_1..12   new/actual by month (editable, detail rows only)
  Q_BUD_1..4  quarterly budget (sum of 3 BUD months)
  Q_NEW_1..4  quarterly new (sum of 3 NEW months, auto-recalculated on save)
  Q_VARIANCE_1..4  = Q_BUD - Q_NEW (auto-recalculated)
  YEAR_BUD / YEAR_NEW / YEAR_VARIANCE  annual totals

Row hierarchy:
  ROW_HEADER_LEVEL = 0 → grand-total row (read-only, auto-updated)
  ROW_HEADER_LEVEL = 1 → detail/editable row

Improvements over Power Apps version:
  - All 4 quarters visible as switchable tabs (no page reload)
  - Inline cell editing with AJAX save and optimistic UI update
  - Grand-total rows auto-recalculate on the client after each save
  - Year selector to view/plan multiple fiscal years
  - Read-only view for non-admin users
"""
from flask import Blueprint, render_template, session, jsonify, request
from auth import login_required
from modules import MODULES, APP_ID_MAP
import sys
from helpers import load_env, SafeConnection

sam_ad_spend_bp = Blueprint("sam_ad_spend", __name__, url_prefix="/sam-ad-spend")

APP_ID   = 10
APP_NAME = "SAM Ad Spend Planning"

# Month names used for column headers
MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun",
               "Jul","Aug","Sep","Oct","Nov","Dec"]

# Quarter → 1-based month indices
QUARTER_MONTHS = {1: [1,2,3], 2: [4,5,6], 3: [7,8,9], 4: [10,11,12]}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_env():
    return load_env()

def _is_admin(email: str) -> bool:
    env  = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        rows = conn.fetchall(
            "SELECT 1 FROM dbo.APP_ADMINS WHERE APP_ID=? AND LOWER(ADMIN_EMAIL)=?",
            (APP_ID, email.lower())
        )
        return len(rows) > 0
    finally:
        conn.close()

def _get_user() -> dict:
    return session.get("user", {})

# ── Routes ────────────────────────────────────────────────────────────────────

@sam_ad_spend_bp.route("/")
@login_required
def index():
    user = _get_user()
    is_admin = _is_admin(user.get("email", ""))
    return render_template(
        "sam_ad_spend.html",
        user=user,
        modules=MODULES,
        active_module="sam_ad_spend_planning",
        is_admin=is_admin,
        month_names=MONTH_NAMES,
        version="4.0",
    )


@sam_ad_spend_bp.route("/api/properties")
@login_required
def api_properties():
    env  = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        rows = conn.fetchall("""
            SELECT PROPERTY_KEY, PROPERTY_NAME
            FROM   dbo.PROPERTY_0
            WHERE  FLAG_REPORTABLE = 1
              AND  FLAG_DISPOSITIONED = 0
            ORDER  BY PROPERTY_NAME
        """)
        return jsonify([{"key": r[0], "name": r[1]} for r in rows])
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        conn.close()


@sam_ad_spend_bp.route("/api/years")
@login_required
def api_years():
    env  = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        rows = conn.fetchall("""
            SELECT DISTINCT YEAR
            FROM   dbo.SAM_GL_WORKTABLE
            WHERE  YEAR IS NOT NULL
            ORDER  BY YEAR DESC
        """)
        return jsonify([r[0] for r in rows])
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        conn.close()


@sam_ad_spend_bp.route("/api/worktable")
@login_required
def api_worktable():
    prop_key = request.args.get("property_key", type=int)
    year     = request.args.get("year", type=int)
    if not prop_key or not year:
        return jsonify({"error": "property_key and year are required"}), 400

    COL_NAMES = [
        "ID","GL_KEY","GL_CODE","GL_NAME","GL_NAME_NUMBER",
        "GL_TYPE","GL_SUB_0","GL_SUB_1","GL_SUB_2",
        "GL_COORDINATES","ROW_HEADER","ROW_HEADER_INDENTED","ROW_HEADER_LEVEL",
        "BUD_1","BUD_2","BUD_3","BUD_4","BUD_5","BUD_6",
        "BUD_7","BUD_8","BUD_9","BUD_10","BUD_11","BUD_12",
        "NEW_1","NEW_2","NEW_3","NEW_4","NEW_5","NEW_6",
        "NEW_7","NEW_8","NEW_9","NEW_10","NEW_11","NEW_12",
        "Q_BUD_1","Q_BUD_2","Q_BUD_3","Q_BUD_4",
        "Q_NEW_1","Q_NEW_2","Q_NEW_3","Q_NEW_4",
        "Q_VARIANCE_1","Q_VARIANCE_2","Q_VARIANCE_3","Q_VARIANCE_4",
        "YEAR_BUD","YEAR_NEW","YEAR_VARIANCE",
    ]
    STR_COLS = {"ID","GL_KEY","GL_CODE","GL_NAME","GL_NAME_NUMBER",
                "GL_TYPE","GL_SUB_0","GL_SUB_1","GL_SUB_2",
                "GL_COORDINATES","ROW_HEADER","ROW_HEADER_INDENTED"}

    env  = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        rows = conn.fetchall("""
            SELECT
                ID, GL_KEY, GL_CODE, GL_NAME, GL_NAME_NUMBER,
                GL_TYPE, GL_SUB_0, GL_SUB_1, GL_SUB_2,
                GL_COORDINATES, ROW_HEADER, ROW_HEADER_INDENTED, ROW_HEADER_LEVEL,
                BUD_1,  BUD_2,  BUD_3,  BUD_4,  BUD_5,  BUD_6,
                BUD_7,  BUD_8,  BUD_9,  BUD_10, BUD_11, BUD_12,
                NEW_1,  NEW_2,  NEW_3,  NEW_4,  NEW_5,  NEW_6,
                NEW_7,  NEW_8,  NEW_9,  NEW_10, NEW_11, NEW_12,
                Q_BUD_1,  Q_BUD_2,  Q_BUD_3,  Q_BUD_4,
                Q_NEW_1,  Q_NEW_2,  Q_NEW_3,  Q_NEW_4,
                Q_VARIANCE_1, Q_VARIANCE_2, Q_VARIANCE_3, Q_VARIANCE_4,
                YEAR_BUD, YEAR_NEW, YEAR_VARIANCE
            FROM  dbo.SAM_GL_WORKTABLE
            WHERE PROPERTY_KEY = ? AND YEAR = ?
            ORDER BY GL_COORDINATES, ROW_HEADER_LEVEL
        """, (prop_key, year))

        result = []
        for row in rows:
            rec = {}
            for col, val in zip(COL_NAMES, row):
                if col in STR_COLS:
                    rec[col] = val or ""
                elif col == "ROW_HEADER_LEVEL":
                    rec[col] = int(val or 0)
                else:
                    try:
                        rec[col] = float(val) if val is not None else 0.0
                    except (TypeError, ValueError):
                        rec[col] = 0.0
            result.append(rec)

        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        conn.close()


@sam_ad_spend_bp.route("/api/update", methods=["POST"])
@login_required
def api_update():
    """Update a single NEW_N cell; recalculates quarterly and annual totals for the GL_CODE group."""
    data      = request.get_json(force=True) or {}
    gl_key    = data.get("gl_key")
    prop_key  = data.get("property_key")
    year      = data.get("year")
    month     = data.get("month")
    new_value = data.get("value", 0)

    if not all([gl_key, prop_key, year, month]):
        return jsonify({"error": "gl_key, property_key, year, month are required"}), 400

    month = int(month)
    if month < 1 or month > 12:
        return jsonify({"error": "month must be 1-12"}), 400

    try:
        new_value = float(new_value)
    except (TypeError, ValueError):
        return jsonify({"error": "value must be numeric"}), 400

    col_new  = f"NEW_{month}"
    quarter  = (month - 1) // 3 + 1
    q_months = [(quarter - 1) * 3 + i for i in range(1, 4)]

    env  = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        # 1. Update the individual cell
        conn.execute(
            f"UPDATE dbo.SAM_GL_WORKTABLE SET {col_new}=? "
            "WHERE GL_KEY=? AND PROPERTY_KEY=? AND YEAR=? AND ROW_HEADER_LEVEL<>0",
            (new_value, gl_key, prop_key, year)
        )

        # 2. Fetch GL_CODE to recalculate its grand-total row
        code_rows = conn.fetchall(
            "SELECT GL_CODE FROM dbo.SAM_GL_WORKTABLE WHERE GL_KEY=? AND PROPERTY_KEY=? AND YEAR=?",
            (gl_key, prop_key, year)
        )
        if not code_rows:
            return jsonify({"success": True})
        gl_code = code_rows[0][0]

        # 3. Sum detail rows for affected quarter + full year
        q_new_cols = ", ".join([f"SUM(ISNULL(NEW_{m},0))" for m in q_months])
        year_cols  = ", ".join([f"SUM(ISNULL(NEW_{m},0))" for m in range(1, 13)])
        agg_rows = conn.fetchall(
            f"SELECT {q_new_cols}, {year_cols} "
            "FROM dbo.SAM_GL_WORKTABLE "
            "WHERE GL_CODE=? AND PROPERTY_KEY=? AND YEAR=? AND ROW_HEADER_LEVEL<>0",
            (gl_code, prop_key, year)
        )

        if agg_rows:
            agg       = agg_rows[0]
            q_new_sum = sum(float(agg[i] or 0) for i in range(3))
            year_new  = sum(float(agg[i] or 0) for i in range(3, 15))
            col_q_new = f"Q_NEW_{quarter}"
            col_q_var = f"Q_VARIANCE_{quarter}"

            bud_rows = conn.fetchall(
                f"SELECT Q_BUD_{quarter}, YEAR_BUD FROM dbo.SAM_GL_WORKTABLE "
                "WHERE GL_CODE=? AND PROPERTY_KEY=? AND YEAR=? AND ROW_HEADER_LEVEL=0",
                (gl_code, prop_key, year)
            )
            q_bud    = float(bud_rows[0][0] or 0) if bud_rows else 0.0
            year_bud = float(bud_rows[0][1] or 0) if bud_rows else 0.0

            conn.execute(
                f"UPDATE dbo.SAM_GL_WORKTABLE "
                f"SET {col_q_new}=?, {col_q_var}=?, YEAR_NEW=?, YEAR_VARIANCE=? "
                "WHERE GL_CODE=? AND PROPERTY_KEY=? AND YEAR=? AND ROW_HEADER_LEVEL=0",
                (q_new_sum, q_bud - q_new_sum, year_new, year_bud - year_new,
                 gl_code, prop_key, year)
            )

        return jsonify({"success": True})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        conn.close()


@sam_ad_spend_bp.route("/api/admins")
@login_required
def api_admins_get():
    env  = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        rows = conn.fetchall(
            "SELECT ID, ADMIN_EMAIL, DATE_CREATED FROM dbo.APP_ADMINS WHERE APP_ID=? ORDER BY ID",
            (APP_ID,)
        )
        return jsonify([{"id": r[0], "email": r[1], "created": str(r[2])} for r in rows])
    finally:
        conn.close()


@sam_ad_spend_bp.route("/api/admins", methods=["POST"])
@login_required
def api_admins_post():
    user = _get_user()
    if not _is_admin(user.get("email", "")):
        return jsonify({"error": "Unauthorized"}), 403
    email = (request.get_json(force=True) or {}).get("email", "").strip().lower()
    if not email:
        return jsonify({"error": "Email required"}), 400
    env  = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute(
            "IF NOT EXISTS (SELECT 1 FROM dbo.APP_ADMINS WHERE APP_ID=? AND LOWER(ADMIN_EMAIL)=?) "
            "INSERT INTO dbo.APP_ADMINS (APP_ID, APP_NAME, ADMIN_EMAIL, DATE_CREATED) VALUES (?,?,?,GETDATE())",
            (APP_ID, email, APP_ID, APP_NAME, email)
        )
        return jsonify({"success": True})
    finally:
        conn.close()


@sam_ad_spend_bp.route("/api/admins/<int:admin_id>", methods=["DELETE"])
@login_required
def api_admins_delete(admin_id):
    user = _get_user()
    if not _is_admin(user.get("email", "")):
        return jsonify({"error": "Unauthorized"}), 403
    env  = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute(
            "DELETE FROM dbo.APP_ADMINS WHERE ID=? AND APP_ID=?",
            (admin_id, APP_ID)
        )
        return jsonify({"success": True})
    finally:
        conn.close()
