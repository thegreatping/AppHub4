import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import SafeConnection, load_env
env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# COMP_ASSIGNMENTS columns
rows = conn.execute("""
    SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
    FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'COMP_ASSIGNMENTS'
    ORDER BY ORDINAL_POSITION
""").fetchall()
print("=== COMP_ASSIGNMENTS ===")
for r in rows:
    print(f"  {r[0]}  ({r[1]}, max={r[2]})")

# Sample
rows = conn.execute("""
    SELECT TOP 10 PARENT_PROPERTY_KEY, PARENT_PROPERTY_NAME,
           COMP_PROPERTY_KEY, COMP_PROPERTY_NAME, RANK_ORDER, DATE_KEY
    FROM COMP_ASSIGNMENTS
    ORDER BY PARENT_PROPERTY_KEY, DATE_KEY DESC, RANK_ORDER
""").fetchall()
print("\n=== SAMPLE COMP_ASSIGNMENTS ===")
for r in rows:
    print(f"  {r}")

# How many distinct parent properties have assignments?
rows = conn.execute("""
    SELECT COUNT(DISTINCT PARENT_PROPERTY_KEY) cnt_parents,
           COUNT(DISTINCT COMP_PROPERTY_KEY) cnt_comps,
           COUNT(*) cnt_total,
           MAX(DATE_KEY) latest_week
    FROM COMP_ASSIGNMENTS
""").fetchall()
print(f"\nStats: {rows[0]}")

# PARENT_PROPERTY columns (subset)
rows = conn.execute("""
    SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'PARENT_PROPERTY' ORDER BY ORDINAL_POSITION
""").fetchall()
print("\n=== PARENT_PROPERTY COLUMNS ===")
for r in rows:
    print(f"  {r[0]}  ({r[1]})")

conn.close()
