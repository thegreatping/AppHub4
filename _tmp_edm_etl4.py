import sys, os
sys.path.insert(0, r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts')
from helpers import load_env, SafeConnection
env = load_env()

conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Where in EMPLOYEE_PREHIRES_APPSUPPORT_SP are EMP_ENTRATA_TITLE_GROUP_MAPPING and EMP_TITLE_GROUP_MGMT used?
sp = conn.fetchall("SELECT definition FROM sys.sql_modules WHERE OBJECT_NAME(object_id) = 'EMPLOYEE_PREHIRES_APPSUPPORT_SP'")
text = sp[0][0]

# Find relevant sections
for tbl in ['EMP_ENTRATA_TITLE_GROUP_MAPPING', 'EMP_TITLE_GROUP_MGMT']:
    idx = text.find(tbl)
    if idx >= 0:
        start = max(0, idx - 200)
        end = min(len(text), idx + 300)
        print(f"\n=== {tbl} context in EMPLOYEE_PREHIRES_APPSUPPORT_SP ===")
        print(text[start:end])
        print("---")

# Also check EMPLOYEE_TITLES_0 reference in any SP across the db  
print("\n=== Where is EMPLOYEE_TITLES_0 used? ===")
refs = conn.fetchall("""
    SELECT DISTINCT OBJECT_NAME(object_id) as obj_name, o.type_desc
    FROM sys.sql_modules m
    JOIN sys.objects o ON o.object_id = m.object_id
    WHERE m.definition LIKE '%EMPLOYEE_TITLES_0%'
""")
for r in refs:
    print(f"  {r[0]} ({r[1]})")

# Check EMPLOYEE_TITLE_GROUPS_0 usage
print("\n=== Where is EMPLOYEE_TITLE_GROUPS_0 used? ===")
refs = conn.fetchall("""
    SELECT DISTINCT OBJECT_NAME(object_id) as obj_name, o.type_desc
    FROM sys.sql_modules m
    JOIN sys.objects o ON o.object_id = m.object_id
    WHERE m.definition LIKE '%EMPLOYEE_TITLE_GROUPS_0%'
""")
for r in refs:
    print(f"  {r[0]} ({r[1]})")

conn.close()
