"""Check EMPLOYEE_F columns and title group data."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection, setup_logger

env = load_env()
log = setup_logger("emp_f_check")

conn = SafeConnection(env, "WH_STAGING", log)

print("=" * 60)
print("EMPLOYEE_F — Columns")
print("=" * 60)
rows = conn.fetchall("""
    SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'EMPLOYEE_F' AND TABLE_SCHEMA = 'dbo'
    ORDER BY ORDINAL_POSITION
""")
for r in rows:
    print(f"  {r[0]:<40s} | {r[1]:<15s} | {r[2] or ''}")

print("\n" + "=" * 60)
print("EMPLOYEE_F — Title Group distinct values (active employees)")
print("=" * 60)
rows = conn.fetchall("""
    SELECT TITLE_GROUP, COUNT(*) as cnt
    FROM dbo.EMPLOYEE_F
    WHERE FLAG_ACTIVE = 1
    GROUP BY TITLE_GROUP
    ORDER BY cnt DESC
""")
for r in rows:
    print(f"  {(r[0] or '(null)'):<40s} | {r[1]} employees")

print("\n" + "=" * 60)
print("EMPLOYEE_F — Sample row (Craig Pell)")
print("=" * 60)
rows = conn.fetchall("""
    SELECT TOP 1 EMAIL, NAME_FULL, TITLE, TITLE_GROUP, EMPLOYEE_CODE, FLAG_ACTIVE
    FROM dbo.EMPLOYEE_F
    WHERE EMAIL LIKE '%cpell%'
""")
for r in rows:
    print(f"  Email: {r[0]}")
    print(f"  Name:  {r[1]}")
    print(f"  Title: {r[2]}")
    print(f"  Group: {r[3]}")
    print(f"  Code:  {r[4]}")
    print(f"  Active: {r[5]}")

conn.close()
print("\nDone.")
