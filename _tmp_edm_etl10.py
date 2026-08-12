import sys, os
sys.path.insert(0, r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts')
from helpers import load_env, SafeConnection
env = load_env()

conn = SafeConnection(env, "WH_STAGING", None)

# DEEP EVAL: How does EMPLOYEE_F_COMBO_SP use EMP_TITLE_GROUP_MGMT?
sp = conn.fetchall("SELECT definition FROM sys.sql_modules WHERE OBJECT_NAME(object_id) = 'EMPLOYEE_F_COMBO_SP'")
text = sp[0][0]

# Find EMP_TITLE_GROUP_MGMT usage
import re
for tbl in ['EMP_TITLE_GROUP_MGMT', 'EMPLOYEE_TITLES_0']:
    idx = text.find(tbl)
    if idx >= 0:
        start = max(0, idx - 400)
        end = min(len(text), idx + 600)
        print(f"\n=== {tbl} in EMPLOYEE_F_COMBO_SP ===")
        print(text[start:end])
        print("---")

# Now: does anything downstream READ the TITLE_GROUP column from EMPLOYEE_F?
# Check what consumes EMPLOYEE_F
print("\n=== SPs that reference EMPLOYEE_F (direct consumers) ===")
refs = conn.fetchall("""
    SELECT DISTINCT OBJECT_NAME(m.object_id)
    FROM sys.sql_modules m
    WHERE m.definition LIKE '%EMPLOYEE[_]F%'
      AND OBJECT_NAME(m.object_id) NOT LIKE '%EMPLOYEE_F%'
""")
for r in refs:
    print(f"  {r[0]}")

# Check specifically who uses TITLE_GROUP from EMPLOYEE_F
print("\n=== SPs referencing TITLE_GROUP ===")
refs = conn.fetchall("""
    SELECT DISTINCT OBJECT_NAME(m.object_id)
    FROM sys.sql_modules m
    WHERE m.definition LIKE '%TITLE_GROUP%'
""")
for r in refs:
    print(f"  {r[0]}")

conn.close()
