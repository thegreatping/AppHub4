"""Sanity check MODULE_AUDIENCE access for different user profiles."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection, setup_logger

env = load_env()
log = setup_logger("chk_access")
dbas = SafeConnection(env, "DB_APP_SUPPORT", log, direct=True)

def check_access(title_group, email=None):
    """Simulate the access check query."""
    params = [title_group, title_group]
    email_clause = ""
    if email:
        email_clause = "OR (ma.GRANT_TYPE IN ('individual','developer') AND ma.GRANT_VALUE = ?)"
        params.append(email)
    
    sql = f"""
        SELECT DISTINCT al.App_Name, 
            MAX(CASE WHEN ma.ACCESS_LEVEL = 'admin' THEN 'admin' 
                     WHEN ma.ACCESS_LEVEL = 'developer' THEN 'developer'
                     ELSE 'user' END) as access
        FROM dbo.MODULE_AUDIENCE ma
        JOIN dbo.APP_LIST al ON (al.App_ID = ma.MODULE_ID OR ma.MODULE_ID = 0)
        WHERE al.Flag_Active = 1
          AND (
            (ma.GRANT_TYPE = 'title_group' AND ma.GRANT_VALUE = ?)
            OR (ma.GRANT_TYPE = 'title_prefix' AND ? LIKE ma.GRANT_VALUE + '%')
            OR (ma.GRANT_VALUE = '*')
            {email_clause}
          )
        GROUP BY al.App_Name
        ORDER BY al.App_Name
    """
    return dbas.fetchall(sql, params)

print("=" * 60)
print("Craig Pell — CORPORATE DIRECTOR + developer")
print("=" * 60)
rows = check_access("CORPORATE DIRECTOR", "cpell@peakmade.com")
print(f"  Modules visible: {len(rows)}")
for r in rows:
    print(f"    {r[0]:<35s} | {r[1]}")

print("\n" + "=" * 60)
print("A Leasing Consultant (no individual grants)")
print("=" * 60)
rows = check_access("PROPERTY LEASING CONSULTANT")
print(f"  Modules visible: {len(rows)}")
for r in rows:
    print(f"    {r[0]:<35s} | {r[1]}")

print("\n" + "=" * 60)
print("A Regional Manager")
print("=" * 60)
rows = check_access("REGIONAL MANAGER")
print(f"  Modules visible: {len(rows)}")
for r in rows:
    print(f"    {r[0]:<35s} | {r[1]}")

print("\n" + "=" * 60)
print("Is developer check for cpell")
print("=" * 60)
dev = dbas.fetchall("""
    SELECT 1 FROM dbo.MODULE_AUDIENCE
    WHERE GRANT_TYPE = 'developer' AND GRANT_VALUE = 'cpell@peakmade.com'
""")
print(f"  is_developer: {len(dev) > 0}")

dbas.close()
