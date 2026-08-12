"""Check PROPERTY_0 for CS columns and EMPLOYEE_SECURITY_0 for relevant TITLE_GROUPs."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# 1. Check if CS columns already exist in PROPERTY_0
print("=== PROPERTY_0 columns containing 'CS' or 'AM' ===")
cur = conn.execute("""
    SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='PROPERTY_0'
      AND (COLUMN_NAME LIKE '%CS%' OR COLUMN_NAME LIKE 'AM%')
    ORDER BY ORDINAL_POSITION
""")
for r in cur.fetchall():
    print(f"  {r[0]:40s}  {r[1]}({r[2]})" if r[2] else f"  {r[0]:40s}  {r[1]}")

# 2. All TITLE_GROUP values in EMPLOYEE_SECURITY_0
print("\n=== TITLE_GROUP values in EMPLOYEE_SECURITY_0 (active employees) ===")
cur = conn.execute("""
    SELECT TITLE_GROUP, COUNT(*) as cnt
    FROM dbo.EMPLOYEE_SECURITY_0
    WHERE FLAG_ACTIVE = 1
    GROUP BY TITLE_GROUP
    ORDER BY TITLE_GROUP
""")
for r in cur.fetchall():
    print(f"  {str(r[0] or 'NULL'):40s}  {r[1]} employees")

# 3. Sample of employees with AM in title group
print("\n=== Sample employees with AM-like TITLE_GROUP ===")
cur = conn.execute("""
    SELECT TOP 10 NAME_FULL, TITLE, TITLE_GROUP, EMAIL
    FROM dbo.EMPLOYEE_SECURITY_0
    WHERE FLAG_ACTIVE = 1
      AND (UPPER(TITLE_GROUP) LIKE '%AREA%' OR UPPER(TITLE_GROUP) LIKE '%REGIONAL%' OR UPPER(TITLE_GROUP) LIKE '%MANAGER%')
    ORDER BY TITLE_GROUP, NAME_FULL
""")
for r in cur.fetchall():
    print(f"  {r[0]:30s}  {r[1]:35s}  {r[2]:25s}  {r[3] or ''}")
