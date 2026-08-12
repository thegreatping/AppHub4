import sys, os
sys.path.insert(0, r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts')
from helpers import load_env, SafeConnection
env = load_env()

conn = SafeConnection(env, "WH_STAGING", None)

# Check: who loads EMPLOYEE_TITLES_0? We know no SP writes to it.
# Check if there's a shortcut table / mirrored table in WH_STAGING from DB_APP_SUPPORT
# via Fabric Mirroring / LCR sync
print("=== Check if EMPLOYEE_TITLES_0 is in sync_tables schema ===")
rows = conn.fetchall("""
    SELECT TABLE_SCHEMA, TABLE_NAME
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME = 'EMPLOYEE_TITLES_0'
""")
for r in rows:
    print(f"  {r[0]}.{r[1]}")

# Check the sync_tables schema for EDM-related tables
print("\n=== sync_tables schema - what's synced from DB_APP_SUPPORT? ===")
rows = conn.fetchall("""
    SELECT TABLE_NAME
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'sync_tables'
    ORDER BY TABLE_NAME
""")
for r in rows:
    print(f"  {r[0]}")

# Also check: What does EMPLOYEE_F.TITLE_GROUP actually get set to?
# In EMPLOYEE_F_COMBO_SP, how does the final TITLE_GROUP get resolved?
sp = conn.fetchall("SELECT definition FROM sys.sql_modules WHERE OBJECT_NAME(object_id) = 'EMPLOYEE_F_COMBO_SP'")
text = sp[0][0]

# Find the main employee build that sets TITLE_GROUP
import re
# Look for where TITLE_GROUP is assigned in the final output
for m in re.finditer(r'TITLE_GROUP_RESOLVED|TITLE_GROUP\b', text[5000:]):
    ctx = text[5000+max(0,m.start()-60):5000+min(len(text)-5000,m.end()+100)]
    if 'ISNULL' in ctx or 'COALESCE' in ctx or 'JOIN' in ctx or 'AS TITLE' in ctx:
        print(f"\n  ...{ctx}...")

conn.close()
