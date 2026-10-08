"""
Security module — resolves user access from MODULE_AUDIENCE + EMPLOYEE_F.

Resolution order:
1. individual/developer grants (exact email match)
2. title_group grants (exact title group match)
3. title_prefix grants (starts-with match on title group)
4. baseline (*) grants
"""
import json
import sys
from helpers import load_env, SafeConnection

_env = None
_log = None

# Title groups whose members are AppHub developers as a group (admin on every
# module + dev tools), in addition to any individual MODULE_AUDIENCE 'developer'
# grants. Future members of these groups become developers automatically.
_DEV_TITLE_GROUPS = {"BUSINESS INTELLIGENCE"}


def _get_env():
    global _env
    if _env is None:
        _env = load_env()
    return _env


def _shadow_log(caller, email, primary, shadow):
    """Compare primary (EMPLOYEE_F) vs shadow (Emp_Core) results and log any
    disagreement to dbo.APPHUB_SECURITY_SHADOW_LOG. Best-effort -- never
    raises, never blocks. Part of the security.py cutover to Emp_Core
    (checklist i-4-47): dual-read while in shadow mode, act on primary only,
    review the log after a few days of quiet before flipping the switch."""
    try:
        primary_found = primary is not None
        shadow_found = shadow is not None
        disagreements = {}
        if primary_found and shadow_found:
            for k in ("name", "title_group", "employee_code", "property", "active"):
                pv, sv = primary.get(k), shadow.get(k)
                if pv != sv:
                    disagreements[k] = {"primary": str(pv)[:200], "shadow": str(sv)[:200]}
        agreed = (primary_found == shadow_found) and not disagreements
        if agreed:
            return
        env = _get_env()
        conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
        try:
            conn.execute(
                "INSERT INTO dbo.APPHUB_SECURITY_SHADOW_LOG "
                "(CALLER, EMAIL, PRIMARY_FOUND, SHADOW_FOUND, AGREED, DISAGREEMENTS_JSON) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (caller, email, 1 if primary_found else 0,
                 1 if shadow_found else 0, 1 if agreed else 0,
                 json.dumps(disagreements)[:4000] if disagreements else None))
        finally:
            conn.close()
    except Exception:
        pass


def _fetch_employee_from_emp_core(email):
    """Emp_Core equivalent of get_employee_info's EMPLOYEE_F read. Wrapped
    so a shadow-side failure never impacts the primary read path."""
    try:
        env = _get_env()
        conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
        try:
            rows = conn.fetchall("""
                SELECT TOP 1 EMAIL, NAME_FULL, TITLE_GROUP, EMPLOYEE_CODE,
                       PROPERTY_NAME, FLAG_ACTIVE
                FROM dbo.Emp_Core
                WHERE LOWER(EMAIL) = ? AND FLAG_ACTIVE = 1
            """, (email.lower(),))
            if rows:
                r = rows[0]
                return {
                    "email": r[0], "name": r[1], "title_group": r[2] or "",
                    "employee_code": r[3], "property": r[4], "active": r[5],
                }
            return None
        finally:
            conn.close()
    except Exception:
        return None


def get_employee_info(email):
    """Look up employee by email in EMPLOYEE_F. Returns dict or None.
    Shadow-compare active: also queries Emp_Core, logs any disagreement to
    dbo.APPHUB_SECURITY_SHADOW_LOG. Return value from EMPLOYEE_F only."""
    if not email or not email.strip():
        return None
    env = _get_env()
    conn = SafeConnection(env, "WH_STAGING", None)
    try:
        rows = conn.fetchall("""
            SELECT TOP 1 EMAIL, NAME_FULL, TITLE_GROUP, EMPLOYEE_CODE, 
                   PROPERTY_NAME, FLAG_ACTIVE
            FROM dbo.EMPLOYEE_F
            WHERE LOWER(EMAIL) = ? AND FLAG_ACTIVE = 1
        """, (email.lower(),))
        primary = None
        if rows:
            r = rows[0]
            primary = {
                "email": r[0],
                "name": r[1],
                "title_group": r[2] or "",
                "employee_code": r[3],
                "property": r[4],
                "active": r[5],
            }
    finally:
        conn.close()

    shadow = _fetch_employee_from_emp_core(email)
    _shadow_log("get_employee_info", email, primary, shadow)
    return primary


def resolve_access(title_group, email):
    """
    Resolve which modules a user can access and their role in each.
    Respects 'exclude' grants that override group-level access.
    Returns: {
        "modules": [{"id": int, "name": str, "access": "user"|"admin"}],
        "is_developer": bool,
    }
    """
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    try:
        params = [title_group, title_group, email.lower()]
        rows = conn.fetchall("""
            SELECT DISTINCT al.App_ID, al.App_Name,
                MAX(CASE WHEN ma.ACCESS_LEVEL = 'admin' THEN 3
                         WHEN ma.ACCESS_LEVEL = 'developer' THEN 4
                         ELSE 1 END) as access_rank
            FROM dbo.MODULE_AUDIENCE ma
            JOIN dbo.APP_LIST al ON (al.App_ID = ma.MODULE_ID OR ma.MODULE_ID = 0)
            WHERE al.Flag_Active = 1
              AND (
                (ma.GRANT_TYPE = 'title_group' AND ma.GRANT_VALUE = ?)
                OR (ma.GRANT_TYPE = 'title_prefix' AND ? LIKE ma.GRANT_VALUE + '%')
                OR (ma.GRANT_TYPE IN ('individual', 'developer') AND ma.GRANT_VALUE = ?)
                OR (ma.GRANT_VALUE = '*')
              )
            GROUP BY al.App_ID, al.App_Name
            ORDER BY al.App_Name
        """, params)

        # Get exclusions for this user
        excl_rows = conn.fetchall("""
            SELECT MODULE_ID FROM dbo.MODULE_AUDIENCE
            WHERE GRANT_TYPE = 'exclude' AND LOWER(GRANT_VALUE) = ?
        """, (email.lower(),))
        excluded_ids = {r[0] for r in excl_rows}

        modules = []
        for r in rows:
            if r[0] in excluded_ids:
                continue  # Skip excluded modules
            access = "user"
            if r[2] == 3:
                access = "admin"
            elif r[2] == 4:
                access = "admin"  # developers get admin everywhere
            modules.append({"id": r[0], "name": r[1], "access": access})

        # Check developer status
        dev_rows = conn.fetchall("""
            SELECT 1 FROM dbo.MODULE_AUDIENCE
            WHERE GRANT_TYPE = 'developer' AND LOWER(GRANT_VALUE) = ?
        """, (email.lower(),))
        is_developer = len(dev_rows) > 0

        # The Business Intelligence team are developers as a group (covers current
        # and future BI members without a per-person MODULE_AUDIENCE grant).
        if (title_group or "").strip().upper() in _DEV_TITLE_GROUPS:
            is_developer = True

        return {
            "modules": modules,
            "is_developer": is_developer,
        }
    finally:
        conn.close()


def _shadow_log_employees_list(primary_rows, shadow_rows):
    """Summary-level shadow log for get_all_active_employees. Compares the
    two full result sets by EMAIL set-difference (not per-row cell diff --
    that would be tens of thousands of comparisons per dropdown load).
    Logs only when counts differ or any email is missing on either side."""
    try:
        primary_emails = {(r.get("email") or "").lower() for r in primary_rows if r.get("email")}
        shadow_emails = {(r.get("email") or "").lower() for r in shadow_rows if r.get("email")}
        only_primary = primary_emails - shadow_emails
        only_shadow = shadow_emails - primary_emails
        if not only_primary and not only_shadow and len(primary_rows) == len(shadow_rows):
            return
        detail = {
            "primary_count": len(primary_rows),
            "shadow_count": len(shadow_rows),
            "only_primary_sample": sorted(only_primary)[:25],
            "only_shadow_sample": sorted(only_shadow)[:25],
        }
        env = _get_env()
        conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
        try:
            conn.execute(
                "INSERT INTO dbo.APPHUB_SECURITY_SHADOW_LOG "
                "(CALLER, EMAIL, PRIMARY_FOUND, SHADOW_FOUND, AGREED, DISAGREEMENTS_JSON) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("get_all_active_employees", None, 1, 1, 0, json.dumps(detail)[:4000]))
        finally:
            conn.close()
    except Exception:
        pass


def _fetch_active_employees_from_emp_core():
    """Emp_Core equivalent of get_all_active_employees's EMPLOYEE_F read."""
    try:
        env = _get_env()
        conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
        try:
            rows = conn.fetchall("""
                SELECT EMAIL, NAME_FULL, TITLE_GROUP, PROPERTY_NAME
                FROM dbo.Emp_Core
                WHERE FLAG_ACTIVE = 1 AND EMAIL IS NOT NULL AND EMAIL != ''
                ORDER BY NAME_FULL
            """)
            return [{"email": r[0], "name": r[1], "title_group": r[2] or "", "property": r[3] or ""} for r in rows]
        except Exception:
            return []
        finally:
            conn.close()
    except Exception:
        return []


def get_all_active_employees():
    """Get list of all active employees for impersonation dropdown.
    Shadow-compare active: also queries Emp_Core, logs any set-difference
    to dbo.APPHUB_SECURITY_SHADOW_LOG. Return value from EMPLOYEE_F only."""
    env = _get_env()
    conn = SafeConnection(env, "WH_STAGING", None)
    try:
        rows = conn.fetchall("""
            SELECT EMAIL, NAME_FULL, TITLE_GROUP, PROPERTY_NAME
            FROM dbo.EMPLOYEE_F
            WHERE FLAG_ACTIVE = 1 AND EMAIL IS NOT NULL AND EMAIL != ''
            ORDER BY NAME_FULL
        """)
        primary = [{"email": r[0], "name": r[1], "title_group": r[2] or "", "property": r[3] or ""} for r in rows]
    finally:
        conn.close()

    shadow = _fetch_active_employees_from_emp_core()
    _shadow_log_employees_list(primary, shadow)
    return primary
