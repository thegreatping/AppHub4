"""Deep dive into weekly leasing tables for the Leasing Trend chart."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# L0_STATIC_HISTORY_BY_WEEK
print("=== L0_STATIC_HISTORY_BY_WEEK columns ===")
cur = conn.execute("SELECT TOP 0 * FROM dbo.L0_STATIC_HISTORY_BY_WEEK")
cols = [d[0] for d in cur.description]
print("  ", cols)
print("\n  Sample rows for 48 WEST (9797):")
cur = conn.execute("SELECT TOP 5 * FROM dbo.L0_STATIC_HISTORY_BY_WEEK WHERE PROPERTY_KEY=9797 ORDER BY 1 DESC")
for r in cur.fetchall():
    print("  ", dict(zip(cols, r)))

# FORECAST_MS_FLOORPLAN_ACTUALS
print("\n=== FORECAST_MS_FLOORPLAN_ACTUALS columns ===")
cur = conn.execute("SELECT TOP 0 * FROM dbo.FORECAST_MS_FLOORPLAN_ACTUALS")
cols = [d[0] for d in cur.description]
print("  ", cols)
print("\n  Sample rows for 48 WEST (9797) AY=2026:")
cur = conn.execute("SELECT TOP 10 * FROM dbo.FORECAST_MS_FLOORPLAN_ACTUALS WHERE PROPERTY_KEY=9797 AND AY=2026 ORDER BY WEEK_NUMBER")
for r in cur.fetchall():
    print("  ", dict(zip(cols, r)))

# FLOORPLAN_ACTUALS_RENT - what does ROW_NUMBER represent?
print("\n=== FLOORPLAN_ACTUALS_RENT - detail check for 48 WEST fp 26537 ===")
cur = conn.execute("""
    SELECT ROW_NUMBER, AY, FLOORPLAN_KEY, FLOORPLAN,
           LEASED_COUNT_NEW, LEASED_COUNT_RENEWAL, LEASED_COUNT_TOTAL,
           INTERVAL_TYPE_CONFORMED
    FROM dbo.FLOORPLAN_ACTUALS_RENT
    WHERE PROPERTY_KEY=9797 AND FLOORPLAN_KEY=26537 AND AY=2026
    ORDER BY ROW_NUMBER
""")
cols2 = [d[0] for d in cur.description]
for r in cur.fetchall():
    print("  ", dict(zip(cols2, r)))

# Check FLOORPLAN_ACTUALS_RENT for AY=2025 to understand PY1
print("\n=== FLOORPLAN_ACTUALS_RENT - 48 WEST fp 26537 AY=2025 ===")
cur = conn.execute("""
    SELECT TOP 10 ROW_NUMBER, AY, LEASED_COUNT_NEW, LEASED_COUNT_RENEWAL, LEASED_COUNT_TOTAL, INTERVAL_TYPE_CONFORMED
    FROM dbo.FLOORPLAN_ACTUALS_RENT
    WHERE PROPERTY_KEY=9797 AND FLOORPLAN_KEY=26537 AND AY=2025
    ORDER BY ROW_NUMBER
""")
cols3 = [d[0] for d in cur.description]
for r in cur.fetchall():
    print("  ", dict(zip(cols3, r)))

conn.close()
