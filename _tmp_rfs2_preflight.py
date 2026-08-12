"""Pre-flight checks for RFS 2.0 build."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# 1. Next available App_ID
cur = conn.execute("SELECT ISNULL(MAX(App_ID), 0) + 1 AS next_id FROM dbo.APP_LIST")
row = cur.fetchone()
print(f"Next App_ID: {row[0]}")

# 2. Check if FLAG_ARCHIVED already exists on FORECAST_FORECASTS
cur = conn.execute("""
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'dbo'
      AND TABLE_NAME = 'FORECAST_FORECASTS'
      AND COLUMN_NAME = 'FLAG_ARCHIVED'
""")
exists = cur.fetchone()[0]
print(f"FLAG_ARCHIVED exists: {bool(exists)}")

# 3. List all columns on FORECAST_FORECASTS
cur = conn.execute("""
    SELECT COLUMN_NAME, DATA_TYPE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='FORECAST_FORECASTS'
    ORDER BY ORDINAL_POSITION
""")
print("\nFORECAST_FORECASTS columns:")
for r in cur.fetchall():
    print(f"  {r[0]} ({r[1]})")

conn.close()
print("\nDone.")
