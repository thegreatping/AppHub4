import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import SafeConnection, load_env
env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

rows = conn.execute("""
    SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
    FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'COMP_PROPERTY'
    ORDER BY ORDINAL_POSITION
""").fetchall()
print("=== COMP_PROPERTY COLUMNS ===")
for r in rows:
    print(f"  {r[0]}  ({r[1]}, max={r[2]})")

# Sample
rows = conn.execute("SELECT TOP 3 PROPERTY_KEY, PROPERTY_NAME, MARKET_KEY, MARKET_STATE, FLAG_ACTIVE FROM COMP_PROPERTY ORDER BY PROPERTY_NAME").fetchall()
print("\n=== SAMPLE ===")
for r in rows:
    print(f"  {r}")

# Count
rows = conn.execute("SELECT COUNT(*) cnt, SUM(CASE WHEN FLAG_ACTIVE=1 THEN 1 ELSE 0 END) active FROM COMP_PROPERTY").fetchall()
print(f"\nTotal: {rows[0][0]}, Active: {rows[0][1]}")
conn.close()
