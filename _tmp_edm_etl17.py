import sys, os
sys.path.insert(0, r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts')
from helpers import load_env, SafeConnection
env = load_env()

conn = SafeConnection(env, "WH_STAGING", None)

# Check EMPLOYEE_SOFT_TERMINATION_OVERRIDES_STG structure and current content
print("=== EMPLOYEE_SOFT_TERMINATION_OVERRIDES_STG structure ===")
cols = conn.fetchall("""
    SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'EMPLOYEE_SOFT_TERMINATION_OVERRIDES_STG'
    ORDER BY ORDINAL_POSITION
""")
for c in cols:
    print(f"  {c[0]} ({c[1]}, {c[2]})")

print("\n=== Current contents ===")
data = conn.fetchall("SELECT * FROM EMPLOYEE_SOFT_TERMINATION_OVERRIDES_STG")
for r in data:
    print(f"  {r}")
print(f"\n  Total: {len(data)} rows")

conn.close()

# Compare with DB_APP_SUPPORT source
conn2 = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
print("\n=== DB_APP_SUPPORT EMPLOYEE_SOFT_TERMINATION_OVERRIDES (source of truth) ===")
data2 = conn2.fetchall("SELECT EMPLOYEE_CODE, FLAG_SOFT_TERMINATION, NAME_FIRST, NAME_LAST, REASON, IS_ACTIVE, EXPIRES_ON FROM EMPLOYEE_SOFT_TERMINATION_OVERRIDES ORDER BY EMPLOYEE_CODE")
for r in data2:
    print(f"  {r}")
print(f"\n  Total: {len(data2)} rows")
conn2.close()
