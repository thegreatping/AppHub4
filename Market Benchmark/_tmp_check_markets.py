import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import SafeConnection, load_env
env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# MARKETS columns
rows = conn.execute("""
    SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
    FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'MARKETS'
    ORDER BY ORDINAL_POSITION
""").fetchall()
print("=== MARKETS ===")
for r in rows:
    print(f"  {r[0]}  ({r[1]}, max={r[2]})")

# MARKET_FACT columns
rows = conn.execute("""
    SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
    FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'MARKET_FACT'
    ORDER BY ORDINAL_POSITION
""").fetchall()
print("\n=== MARKET_FACT ===")
for r in rows:
    print(f"  {r[0]}  ({r[1]}, max={r[2]})")

# Sample MARKETS
rows = conn.execute("SELECT TOP 5 * FROM MARKETS WHERE MARKET_CITY_STATE != '' ORDER BY MARKET_KEY").fetchall()
print("\n=== SAMPLE MARKETS ===")
for r in rows:
    print(f"  {r}")

# Sample MARKET_FACT
rows = conn.execute("SELECT TOP 5 * FROM MARKET_FACT ORDER BY MARKET_KEY, AY").fetchall()
print("\n=== SAMPLE MARKET_FACT ===")
for r in rows:
    print(f"  {r}")

conn.close()
