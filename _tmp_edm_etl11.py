import sys, os
sys.path.insert(0, r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts')
from helpers import load_env, SafeConnection
env = load_env()

conn = SafeConnection(env, "WH_STAGING", None)

# Get the actual SQL JOIN logic in EMPLOYEE_F_COMBO_SP that uses EMP_TITLE_GROUP_MGMT
sp = conn.fetchall("SELECT definition FROM sys.sql_modules WHERE OBJECT_NAME(object_id) = 'EMPLOYEE_F_COMBO_SP'")
text = sp[0][0]

# Find the actual JOIN (not the header comment) - search after position 2000 to skip comments
idx = text.find('EMP_TITLE_GROUP_MGMT', 2000)
if idx >= 0:
    start = max(0, idx - 500)
    end = min(len(text), idx + 700)
    print("=== EMP_TITLE_GROUP_MGMT actual JOIN in EMPLOYEE_F_COMBO_SP ===")
    print(text[start:end])

# Also find EMPLOYEE_TITLES_0 actual usage
idx = text.find('EMPLOYEE_TITLES_0', 2000)
if idx >= 0:
    start = max(0, idx - 300)
    end = min(len(text), idx + 500)
    print("\n\n=== EMPLOYEE_TITLES_0 actual JOIN ===")
    print(text[start:end])

conn.close()

# For item 6: Check EMPLOYEE_TITLE_GROUPS_0 in WH_STAGING - what columns does it have?
conn2 = SafeConnection(env, "WH_STAGING", None)
print("\n\n=== EMPLOYEE_TITLE_GROUPS_0 structure ===")
cols = conn2.fetchall("""
    SELECT COLUMN_NAME, DATA_TYPE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'EMPLOYEE_TITLE_GROUPS_0'
    ORDER BY ORDINAL_POSITION
""")
for c in cols:
    print(f"  {c[0]} ({c[1]})")

print("\n=== EMPLOYEE_TITLE_GROUPS_0 data (all rows) ===")
data = conn2.fetchall("SELECT * FROM EMPLOYEE_TITLE_GROUPS_0")
for r in data:
    print(f"  {r}")

# Check if any view references this table
print("\n=== Views/SPs referencing EMPLOYEE_TITLE_GROUPS_0 ===")
refs = conn2.fetchall("""
    SELECT DISTINCT OBJECT_NAME(m.object_id), o.type_desc
    FROM sys.sql_modules m
    JOIN sys.objects o ON o.object_id = m.object_id
    WHERE m.definition LIKE '%EMPLOYEE[_]TITLE[_]GROUPS[_]0%'
""")
for r in refs:
    print(f"  {r[0]} ({r[1]})")

conn2.close()
