import sys, os
sys.path.insert(0, r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts')
from helpers import load_env, SafeConnection
env = load_env()

conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Check EMPLOYEE_TITLES_0 usage
print("=== Where is EMPLOYEE_TITLES_0 used? ===")
refs = conn.fetchall("""
    SELECT DISTINCT OBJECT_NAME(m.object_id) as obj_name
    FROM sys.sql_modules m
    WHERE m.definition LIKE '%EMPLOYEE[_]TITLES[_]0%'
""")
for r in refs:
    print(f"  {r[0]}")

# Check EMPLOYEE_TITLE_GROUPS_0 usage
print("\n=== Where is EMPLOYEE_TITLE_GROUPS_0 used? ===")
refs = conn.fetchall("""
    SELECT DISTINCT OBJECT_NAME(m.object_id) as obj_name
    FROM sys.sql_modules m
    WHERE m.definition LIKE '%EMPLOYEE[_]TITLE[_]GROUPS[_]0%'
""")
for r in refs:
    print(f"  {r[0]}")

# Now check WH_STAGING for references too
conn.close()
conn2 = SafeConnection(env, "WH_STAGING", None)

print("\n=== WH_STAGING: SPs referencing EDM tables ===")
for tbl in ['EMP_TITLE_GROUP_MGMT', 'EMPLOYEE_TITLES_0', 'EMPLOYEE_TITLE_GROUPS_0', 'EMP_ENTRATA_TITLE_GROUP_MAPPING']:
    refs = conn2.fetchall(f"""
        SELECT DISTINCT OBJECT_NAME(m.object_id) as obj_name
        FROM sys.sql_modules m
        WHERE m.definition LIKE '%{tbl}%'
    """)
    if refs:
        print(f"\n  {tbl}:")
        for r in refs:
            print(f"    - {r[0]}")
    else:
        print(f"\n  {tbl}: not referenced")

conn2.close()
