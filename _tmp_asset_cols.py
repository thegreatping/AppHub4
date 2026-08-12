import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
cur = conn.execute("""
    SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='PROPERTY_0'
    AND COLUMN_NAME LIKE '%ASSET%'
    ORDER BY ORDINAL_POSITION
""")
print("Asset Manager columns:")
for r in cur.fetchall():
    print(f"  {r[0]}")

# Also check what columns exist that aren't in our known sets
cur2 = conn.execute("""
    SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='PROPERTY_0'
    ORDER BY ORDINAL_POSITION
""")
all_cols = [r[0] for r in cur2.fetchall()]
print(f"\nTotal columns in PROPERTY_0: {len(all_cols)}")
