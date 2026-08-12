"""Investigate AppHub Maintenance module - related tables and audience."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

print("=" * 70)
print("1. APP_LIST TABLE (what the maintenance module edits)")
print("=" * 70)
rows = conn.fetchall("SELECT * FROM dbo.APP_LIST ORDER BY App_ID")
print(f"\nAPP_LIST ({len(rows)} rows):")
print(f"  {'ID':4s} {'Name':40s} {'Level':5s} {'SecLevel':8s} {'Active':6s}")
print(f"  {'-'*4} {'-'*40} {'-'*5} {'-'*8} {'-'*6}")
for r in rows:
    print(f"  {r[0]:<4d} {r[1]:40s} {r[2]:<5d} {r[3]:<8d} {r[4]:<6d}")

print("\n" + "=" * 70)
print("2. EMPLOYEE_TITLE_GROUP_LEVELS_0 (security level definitions)")
print("=" * 70)
levels = conn.fetchall("SELECT * FROM dbo.EMPLOYEE_TITLE_GROUP_LEVELS_0 ORDER BY TITLE_GROUP_SECURITY_LEVEL")
cols = conn.fetchall("""
    SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'EMPLOYEE_TITLE_GROUP_LEVELS_0' ORDER BY ORDINAL_POSITION
""")
print(f"\nColumns: {[c[0] for c in cols]}")
print(f"\nLevels ({len(levels)} rows):")
for r in levels:
    print(f"  {r}")

print("\n" + "=" * 70)
print("3. EMPLOYEE_TITLE_GROUPS_0 (title group -> security level mapping)")
print("=" * 70)
groups = conn.fetchall("SELECT TOP 20 * FROM dbo.EMPLOYEE_TITLE_GROUPS_0 ORDER BY TITLE_GROUP")
grp_cols = conn.fetchall("""
    SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'EMPLOYEE_TITLE_GROUPS_0' ORDER BY ORDINAL_POSITION
""")
print(f"\nColumns: {[c[0] for c in grp_cols]}")
grp_count = conn.fetchall("SELECT COUNT(*) FROM dbo.EMPLOYEE_TITLE_GROUPS_0")
print(f"Total rows: {grp_count[0][0]}")
print(f"\nSample (first 20):")
for r in groups:
    print(f"  {r}")

print("\n" + "=" * 70)
print("4. MODULE_AUDIENCE GRANTS FOR APP_ID 14")
print("=" * 70)
grants = conn.fetchall("""
    SELECT GRANT_TYPE, GRANT_VALUE, ACCESS_LEVEL, COUNT(*) as cnt
    FROM dbo.MODULE_AUDIENCE
    WHERE MODULE_ID = 14
    GROUP BY GRANT_TYPE, GRANT_VALUE, ACCESS_LEVEL
    ORDER BY GRANT_TYPE, GRANT_VALUE
""")
print(f"\nAudience grants for AppHub Maintenance ({len(grants)}):")
for g in grants:
    print(f"  {g[0]:15s} {g[1]:35s} access={g[2]:10s} count={g[3]}")

print("\n" + "=" * 70)
print("5. APP_ADMINS TABLE (if exists)")
print("=" * 70)
try:
    admins = conn.fetchall("SELECT * FROM dbo.APP_ADMINS WHERE APP_ID = 14")
    print(f"\nAdmins for APP_ID 14: {admins}")
except Exception as e:
    print(f"\n  APP_ADMINS table: {e}")

conn.close()
