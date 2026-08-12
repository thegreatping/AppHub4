import sys, os
sys.path.insert(0, r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts')
from helpers import load_env, SafeConnection
env = load_env()

# Check MODULE_AUDIENCE for App_ID 9
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
rows = conn.fetchall("""
    SELECT GRANT_TYPE, GRANT_VALUE, ACCESS_LEVEL
    FROM dbo.MODULE_AUDIENCE
    WHERE MODULE_ID = 9
    ORDER BY GRANT_TYPE, GRANT_VALUE
""")
print("=== MODULE_AUDIENCE for EDM (ID 9) ===")
for r in rows:
    print(f"  {r[0]:15} | {r[1]:30} | {r[2]}")
print(f"\n  Total grants: {len(rows)}")
conn.close()

# Check if there are any EDM-related tables in DB_APP_SUPPORT
conn2 = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
tables = conn2.fetchall("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME LIKE '%EMPLOYEE%' OR TABLE_NAME LIKE '%EDM%' OR TABLE_NAME LIKE '%EMP_DATA%'
    ORDER BY TABLE_NAME
""")
print("\n=== EDM-related tables in DB_APP_SUPPORT ===")
for t in tables:
    print(f"  {t[0]}")
conn2.close()
