import sys, os
sys.path.insert(0, r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts')
from helpers import load_env, SafeConnection
env = load_env()

# Check WH_STAGING for any views/SPs that reference these tables
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Check stored procedures that reference these tables
print("=== Stored Procedures referencing EDM tables ===")
tables_to_check = ['EMP_ENTRATA_TITLE_GROUP_MAPPING', 'EMP_TITLE_GROUP_MGMT', 'EMPLOYEE_SECURITY', 
                   'EMPLOYEE_SECURITY_0', 'EMPLOYEE_TITLE_GROUPS_0', 'EMPLOYEE_TITLES_0',
                   'EMPLOYEE_SOFT_TERMINATION_OVERRIDES', 'EMPLOYEE_SECURITY_ROLES']
for tbl in tables_to_check:
    refs = conn.fetchall(f"""
        SELECT DISTINCT OBJECT_NAME(object_id) as sp_name
        FROM sys.sql_modules
        WHERE definition LIKE '%{tbl}%'
        ORDER BY sp_name
    """)
    if refs:
        print(f"\n  {tbl} referenced by:")
        for r in refs:
            print(f"    - {r[0]}")
    else:
        print(f"\n  {tbl}: NO SP references")

conn.close()
