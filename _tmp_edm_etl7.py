import sys, os
sys.path.insert(0, r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts')
from helpers import load_env, SafeConnection
env = load_env()

# 1. Find soft termination / AD-related tables
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

print("=== DB_APP_SUPPORT: Tables with 'SOFT_TERM' or 'AD' in name ===")
rows = conn.fetchall("""
    SELECT t.name, p.rows
    FROM sys.tables t
    JOIN sys.partitions p ON t.object_id = p.object_id AND p.index_id IN (0,1)
    WHERE t.name LIKE '%SOFT_TERM%' OR t.name LIKE '%ACTIVE_EMP%' OR t.name LIKE '%AD_EXPORT%'
       OR t.name LIKE '%AD_EMPLOYEE%'
    ORDER BY t.name
""")
for r in rows:
    print(f"  {r[0]} ({r[1]} rows)")

# 2. Check what SPs reference soft termination
print("\n=== SPs referencing 'SOFT_TERM' ===")
refs = conn.fetchall("""
    SELECT DISTINCT OBJECT_NAME(m.object_id)
    FROM sys.sql_modules m
    WHERE m.definition LIKE '%SOFT_TERM%'
""")
for r in refs:
    print(f"  {r[0]}")

# 3. Check what SPs reference 'ACTIVE_EMP' or 'AD_EMPLOYEE'
print("\n=== SPs referencing 'ACTIVE_EMP' or 'AD_EMPLOYEE' ===")
refs = conn.fetchall("""
    SELECT DISTINCT OBJECT_NAME(m.object_id)
    FROM sys.sql_modules m
    WHERE m.definition LIKE '%ACTIVE_EMP%' OR m.definition LIKE '%AD_EMPLOYEE%'
""")
for r in refs:
    print(f"  {r[0]}")

conn.close()

# 4. Same search in WH_STAGING
conn2 = SafeConnection(env, "WH_STAGING", None)

print("\n=== WH_STAGING: Tables with 'SOFT_TERM' or 'ACTIVE_EMP' or 'AD' ===")
rows = conn2.fetchall("""
    SELECT t.name, p.rows
    FROM sys.tables t
    JOIN sys.partitions p ON t.object_id = p.object_id AND p.index_id IN (0,1)
    WHERE t.name LIKE '%SOFT_TERM%' OR t.name LIKE '%ACTIVE_EMP%' OR t.name LIKE '%AD_EXPORT%'
       OR t.name LIKE '%AD_EMPLOYEE%'
    ORDER BY t.name
""")
for r in rows:
    print(f"  {r[0]} ({r[1]} rows)")

print("\n=== WH_STAGING: SPs referencing 'SOFT_TERM' ===")
refs = conn2.fetchall("""
    SELECT DISTINCT OBJECT_NAME(m.object_id)
    FROM sys.sql_modules m
    WHERE m.definition LIKE '%SOFT_TERM%'
""")
for r in refs:
    print(f"  {r[0]}")

conn2.close()
