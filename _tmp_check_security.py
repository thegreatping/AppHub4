"""Check the security control tables in DB_App_Support."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection, setup_logger

env = load_env()
log = setup_logger("sec_check")

# Connect to DB_App_Support (direct, per rules)
conn = SafeConnection(env, "DB_APP_SUPPORT", log, direct=True)

print("=" * 60)
print("APP_LIST — Module registry with security levels")
print("=" * 60)
rows = conn.fetchall("SELECT App_ID, App_Name, App_Security_Level, Flag_Active FROM dbo.APP_LIST ORDER BY App_Name")
for r in rows:
    print(f"  {r[0]:3d} | {r[1]:<35s} | Level: {r[2]:3d} | Active: {r[3]}")

print("\n" + "=" * 60)
print("APP_ADMINS — Per-module admin assignments (target modules only)")
print("=" * 60)
rows = conn.fetchall("""
    SELECT APP_ID, APP_NAME, ADMIN_EMAIL, ADMIN_TYPE
    FROM dbo.APP_ADMINS
    WHERE APP_ID IN (20, 22, 24, 25)
    ORDER BY APP_ID, ADMIN_EMAIL
""")
for r in rows:
    print(f"  App {r[0]:2d} ({r[1]:<25s}) | {r[2]:<40s} | Type: {r[3]}")

print("\n" + "=" * 60)
print("EMPLOYEE_SECURITY_0 — Sample of security levels (top 20)")
print("=" * 60)
rows = conn.fetchall("""
    SELECT TOP 20 EMAIL, NAME_FULL, TITLE_GROUP, TITLE_GROUP_SECURITY_LEVEL, FLAG_ACTIVE
    FROM dbo.EMPLOYEE_SECURITY_0
    WHERE FLAG_ACTIVE = 1
    ORDER BY TITLE_GROUP_SECURITY_LEVEL DESC
""")
for r in rows:
    print(f"  Level {r[3] or 0:3d} | {(r[1] or ''):30s} | Group: {(r[2] or ''):20s} | {r[0] or ''}")

print("\n" + "=" * 60)
print("EMPLOYEE_SECURITY_0 — Distinct security levels")
print("=" * 60)
rows = conn.fetchall("""
    SELECT TITLE_GROUP_SECURITY_LEVEL, TITLE_GROUP_DESCRIPTION, COUNT(*) as cnt
    FROM dbo.EMPLOYEE_SECURITY_0
    WHERE FLAG_ACTIVE = 1
    GROUP BY TITLE_GROUP_SECURITY_LEVEL, TITLE_GROUP_DESCRIPTION
    ORDER BY TITLE_GROUP_SECURITY_LEVEL DESC
""")
for r in rows:
    print(f"  Level {r[0] or 0:3d} | {(r[1] or ''):35s} | {r[2]} employees")

print("\n" + "=" * 60)
print("PeakLink table check — does it exist in SQL?")
print("=" * 60)
rows = conn.fetchall("""
    SELECT TABLE_SCHEMA, TABLE_NAME
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME LIKE '%PeakLink%' OR TABLE_NAME LIKE '%PEAKLINK%' OR TABLE_NAME LIKE '%peak_link%'
""")
if rows:
    for r in rows:
        print(f"  Found: {r[0]}.{r[1]}")
else:
    print("  NOT FOUND in DB_App_Support — confirmed SharePoint-only")

# Also check for Cultivate and FastTrack tables
print("\n" + "=" * 60)
print("Target module tables — existence check")
print("=" * 60)
rows = conn.fetchall("""
    SELECT TABLE_SCHEMA, TABLE_NAME
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME IN ('CULTIVATE_NOMINATION', 'FASTTRACK_RECOMMENDATION', 'Peak Mindset Recognition', 'PeakLink')
       OR TABLE_NAME LIKE '%CULTIVATE%' OR TABLE_NAME LIKE '%FASTTRACK%' OR TABLE_NAME LIKE '%MINDSET%'
    ORDER BY TABLE_NAME
""")
for r in rows:
    print(f"  {r[0]}.{r[1]}")

conn.close()
print("\nDone.")
