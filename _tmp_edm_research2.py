import sys, os
sys.path.insert(0, r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts')
from helpers import load_env, SafeConnection
env = load_env()

conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Key tables - check structure
for tbl in ['EMPLOYEE_0', 'EMPLOYEE_TITLE_GROUPS_0', 'EMPLOYEE_TITLES_0', 'EMPLOYEE_TITLE_GROUP_LEVELS_0', 'EMPLOYEE_TITLE_CONTROL_0']:
    cols = conn.fetchall(f"""
        SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = '{tbl}'
        ORDER BY ORDINAL_POSITION
    """)
    print(f"\n=== {tbl} ({len(cols)} cols) ===")
    for c in cols[:15]:
        print(f"  {c[0]:35} {c[1]:12} {c[2] or ''}")
    if len(cols) > 15:
        print(f"  ... +{len(cols)-15} more columns")

# Check row counts
for tbl in ['EMPLOYEE_0', 'EMPLOYEE_TITLE_GROUPS_0', 'EMPLOYEE_TITLES_0', 'EMPLOYEE_TITLE_GROUP_LEVELS_0']:
    cnt = conn.fetchall(f"SELECT COUNT(*) FROM dbo.{tbl}")
    print(f"\n{tbl}: {cnt[0][0]} rows")

conn.close()
