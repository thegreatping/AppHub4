import sys, os
sys.path.insert(0, r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts')
from helpers import load_env, SafeConnection
env = load_env()

conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Check EMPLOYEE_TITLE_CONTROL_0 - this looks like what EDM manages
print("=== EMPLOYEE_TITLE_CONTROL_0 (sample 10 rows) ===")
rows = conn.fetchall("SELECT TOP 10 * FROM dbo.EMPLOYEE_TITLE_CONTROL_0 ORDER BY TITLE")
for r in rows:
    print(f"  Key:{r[0]:4} | {r[1]:40} | Global:{r[2]} Excl:{r[3]} Mile:{r[4]} Mkt:{r[5]}")

# Check EMPLOYEE_TITLE_GROUPS_0
print("\n=== EMPLOYEE_TITLE_GROUPS_0 ===")
rows = conn.fetchall("SELECT * FROM dbo.EMPLOYEE_TITLE_GROUPS_0 ORDER BY TITLE_GROUP")
for r in rows:
    print(f"  Key:{r[0]:3} | {r[1]:35} | Level:{r[2]} OldLevel:{r[3]} | {r[4]}")

# What's in EMPLOYEE_ROLES_1?
print("\n=== EMPLOYEE_ROLES_1 structure ===")
cols = conn.fetchall("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'EMPLOYEE_ROLES_1' ORDER BY ORDINAL_POSITION")
for c in cols:
    print(f"  {c[0]}")
cnt = conn.fetchall("SELECT COUNT(*) FROM dbo.EMPLOYEE_ROLES_1")
print(f"  ({cnt[0][0]} rows)")

conn.close()
