"""
Security module — resolves user access from MODULE_AUDIENCE + EMPLOYEE_F.

Resolution order:
1. individual/developer grants (exact email match)
2. title_group grants (exact title group match)
3. title_prefix grants (starts-with match on title group)
4. baseline (*) grants
"""
import sys
from helpers import load_env, SafeConnection

_env = None
_log = None


def _get_env():
    global _env
    if _env is None:
        _env = load_env()
    return _env


def get_employee_info(email):
    """Look up employee by email in EMPLOYEE_F. Returns dict or None."""
    env = _get_env()
    conn = SafeConnection(env, "WH_STAGING", None)
    try:
        rows = conn.fetchall("""
            SELECT TOP 1 EMAIL, NAME_FULL, TITLE_GROUP, EMPLOYEE_CODE, 
                   PROPERTY_NAME, FLAG_ACTIVE
            FROM dbo.EMPLOYEE_F
            WHERE LOWER(EMAIL) = ? AND FLAG_ACTIVE = 1
        """, (email.lower(),))
        if rows:
            r = rows[0]
            return {
                "email": r[0],
                "name": r[1],
                "title_group": r[2] or "",
                "employee_code": r[3],
                "property": r[4],
                "active": r[5],
            }
        return None
    finally:
        conn.close()


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

        return {
            "modules": modules,
            "is_developer": is_developer,
        }
    finally:
        conn.close()


def get_all_active_employees():
    """Get list of all active employees for impersonation dropdown."""
    env = _get_env()
    conn = SafeConnection(env, "WH_STAGING", None)
    try:
        rows = conn.fetchall("""
            SELECT EMAIL, NAME_FULL, TITLE_GROUP, PROPERTY_NAME
            FROM dbo.EMPLOYEE_F
            WHERE FLAG_ACTIVE = 1 AND EMAIL IS NOT NULL AND EMAIL != ''
            ORDER BY NAME_FULL
        """)
        return [{"email": r[0], "name": r[1], "title_group": r[2] or "", "property": r[3] or ""} for r in rows]
    finally:
        conn.close()
