import sys, os
sys.path.insert(0, r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts')
from helpers import load_env, SafeConnection
env = load_env()

conn = SafeConnection(env, "WH_STAGING", None)

# Get the full ACTIVE_EMPS_FOR_AD_SP to find the soft termination logic
sp = conn.fetchall("SELECT definition FROM sys.sql_modules WHERE OBJECT_NAME(object_id) = 'ACTIVE_EMPS_FOR_AD_SP'")
text = sp[0][0]

# Find all SOFT_TERM references
import re
matches = [(m.start(), m.end()) for m in re.finditer(r'SOFT_TERM', text)]
print(f"Total SOFT_TERM references: {len(matches)}")

# Show each context
for i, (start, end) in enumerate(matches):
    ctx_start = max(0, start - 100)
    ctx_end = min(len(text), end + 200)
    print(f"\n--- Reference {i+1} at pos {start} ---")
    print(text[ctx_start:ctx_end])

# Also find where the OVERRIDES table is used
print("\n\n=== EMPLOYEE_SOFT_TERMINATION_OVERRIDES usage ===")
idx = text.find('EMPLOYEE_SOFT_TERMINATION_OVERRIDES')
if idx >= 0:
    print(text[max(0,idx-200):min(len(text),idx+500)])
else:
    print("NOT FOUND in ACTIVE_EMPS_FOR_AD_SP")

# Check the structure of EMPLOYEE_SOFT_TERMINATION_OVERRIDES in DB_APP_SUPPORT
conn.close()
conn2 = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

print("\n\n=== EMPLOYEE_SOFT_TERMINATION_OVERRIDES structure ===")
cols = conn2.fetchall("""
    SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'EMPLOYEE_SOFT_TERMINATION_OVERRIDES'
    ORDER BY ORDINAL_POSITION
""")
for c in cols:
    print(f"  {c[0]} ({c[1]}, {c[2]})")

print("\n=== Sample data ===")
data = conn2.fetchall("SELECT TOP 5 * FROM EMPLOYEE_SOFT_TERMINATION_OVERRIDES")
for r in data:
    print(f"  {r}")

conn2.close()
