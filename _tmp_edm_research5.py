import sys, os
sys.path.insert(0, r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts')
from helpers import load_env, SafeConnection
env = load_env()

conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Check all schemas for title_control
rows = conn.fetchall("""
    SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME LIKE '%TITLE_CONTROL%' OR TABLE_NAME LIKE '%TITLE_GROUP%'
    ORDER BY TABLE_SCHEMA, TABLE_NAME
""")
print("=== Title-related tables across schemas ===")
for r in rows:
    print(f"  {r[0]}.{r[1]}")

# EMPLOYEE_TITLE_GROUPS_0 and EMPLOYEE_TITLES_0
print("\n=== EMPLOYEE_TITLE_GROUPS_0 ===")
rows = conn.fetchall("SELECT * FROM dbo.EMPLOYEE_TITLE_GROUPS_0 ORDER BY TITLE_GROUP")
for r in rows:
    print(f"  Key:{r[0]:3} | {r[1]:35} | Level:{r[2]} | {r[4] if len(r)>4 else ''}")

print("\n=== EMPLOYEE_TITLES_0 (first 15) ===")
rows = conn.fetchall("SELECT TOP 15 TITLE_KEY, TITLE, TITLE_GROUP, FLAG_ACCESS_GLOBAL, FLAG_ACCESS_MILESTONES FROM dbo.EMPLOYEE_TITLES_0 ORDER BY TITLE")
for r in rows:
    print(f"  Key:{r[0]:4} | {r[1]:40} | {r[2]:25} | Glob:{r[3]} Mile:{r[4]}")

print("\n=== EMPLOYEE_ROLES_1 ===")
cols = conn.fetchall("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'EMPLOYEE_ROLES_1' ORDER BY ORDINAL_POSITION")
for c in cols:
    print(f"  {c[0]}")
rows = conn.fetchall("SELECT TOP 5 * FROM dbo.EMPLOYEE_ROLES_1")
print("  ---sample---")
for r in rows:
    print(f"  {r}")

conn.close()
