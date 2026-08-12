import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Get floorplans from FORECAST_BUDGET_TIERS (unique floorplan per property with total beds)
cur = conn.execute("""
    SELECT FLOORPLAN_KEY, FLOORPLAN_CODE, SUM(BEDS) AS BEDS
    FROM dbo.FORECAST_BUDGET_TIERS
    WHERE PROPERTY_KEY=9797 AND AY=2026
    GROUP BY FLOORPLAN_KEY, FLOORPLAN_CODE
    ORDER BY FLOORPLAN_CODE
""")
print("Floorplans (from budget tiers sum):")
for r in cur.fetchall():
    print(f"  {r}")

# Also check FLOORPLAN_FACT
cur = conn.execute("""
    SELECT DISTINCT PROPERTY_KEY, FLOORPLAN_NAME, FLOORPLAN_BEDS, BED_COUNT
    FROM dbo.FLOORPLAN_FACT
    WHERE PROPERTY_KEY=9797 AND FLAG_ACTIVE=1
""")
print("\nFLOORPLAN_FACT active for 9797:")
for r in cur.fetchall()[:10]:
    print(f"  {r}")

conn.close()
