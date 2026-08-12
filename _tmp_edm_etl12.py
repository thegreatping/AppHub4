import sys, os
sys.path.insert(0, r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts')
from helpers import load_env, SafeConnection
env = load_env()

conn = SafeConnection(env, "WH_STAGING", None)

# EMPLOYEE_TITLES_0 - get full structure and check how it's loaded
print("=== EMPLOYEE_TITLES_0 structure ===")
cols = conn.fetchall("""
    SELECT COLUMN_NAME, DATA_TYPE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'EMPLOYEE_TITLES_0'
    ORDER BY ORDINAL_POSITION
""")
for c in cols:
    print(f"  {c[0]} ({c[1]})")

print(f"\n=== EMPLOYEE_TITLES_0 row count ===")
cnt = conn.fetchall("SELECT COUNT(*) FROM EMPLOYEE_TITLES_0")
print(f"  {cnt[0][0]} rows")

# Check if EMPLOYEE_TITLES_0 is loaded by any SP (is it an output of something?)
print("\n=== SPs that INSERT/UPDATE EMPLOYEE_TITLES_0 ===")
refs = conn.fetchall("""
    SELECT DISTINCT OBJECT_NAME(m.object_id)
    FROM sys.sql_modules m
    WHERE (m.definition LIKE '%INTO%EMPLOYEE[_]TITLES[_]0%'
        OR m.definition LIKE '%UPDATE%EMPLOYEE[_]TITLES[_]0%'
        OR m.definition LIKE '%MERGE%EMPLOYEE[_]TITLES[_]0%')
""")
for r in refs:
    print(f"  {r[0]}")

# What about PAYCOM_IMPORT_EDM_SP?  It references TITLE_GROUP.
print("\n=== PAYCOM_IMPORT_EDM_SP - does it write EMPLOYEE_TITLES_0? ===")
sp = conn.fetchall("SELECT definition FROM sys.sql_modules WHERE OBJECT_NAME(object_id) = 'PAYCOM_IMPORT_EDM_SP'")
if sp:
    text = sp[0][0]
    idx = text.find('EMPLOYEE_TITLES_0')
    if idx >= 0:
        start = max(0, idx - 300)
        end = min(len(text), idx + 500)
        print(text[start:end])
    else:
        # check TITLE_GROUP usage
        idx = text.find('TITLE_GROUP')
        if idx >= 0:
            start = max(0, idx - 200)
            end = min(len(text), idx + 400)
            print(f"EMPLOYEE_TITLES_0 not found, but TITLE_GROUP at pos {idx}:")
            print(text[start:end])

# Where is EMPLOYEE_TITLE_GROUPS_0 populated from? (It's not in any SP output)
# Check if there's a pipeline/notebook that loads it
print("\n=== Who loads EMPLOYEE_TITLE_GROUPS_0? ===")
refs = conn.fetchall("""
    SELECT DISTINCT OBJECT_NAME(m.object_id)
    FROM sys.sql_modules m
    WHERE m.definition LIKE '%INTO%EMPLOYEE[_]TITLE[_]GROUPS[_]0%'
       OR m.definition LIKE '%MERGE%EMPLOYEE[_]TITLE[_]GROUPS[_]0%'
""")
if refs:
    for r in refs:
        print(f"  {r[0]}")
else:
    print("  No SP loads this table - was loaded by BODS (now dead)")

# Check: does the TITLE_GROUP_KEY or TITLE_GROUP_SECURITY_LEVEL from EMPLOYEE_TITLE_GROUPS_0 
# appear anywhere we can trace?
# EMPLOYEE_TITLES_0 has TITLE_GROUP_KEY - is that a FK to EMPLOYEE_TITLE_GROUPS_0?
print("\n=== EMPLOYEE_TITLES_0 sample (5 rows) ===")
data = conn.fetchall("SELECT TOP 5 TITLE, TITLE_GROUP, TITLE_GROUP_KEY, TITLE_GROUP_SECURITY_LEVEL FROM EMPLOYEE_TITLES_0")
for r in data:
    print(f"  {r}")

conn.close()
