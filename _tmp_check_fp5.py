import sys
sys.path.insert(0, '../Help Ticket Triage/bi-triage-agent/scripts')
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, 'DB_APP_SUPPORT', None, direct=True)

# Option 1: distinct floorplans from FORECAST_BUDGET_TIERS + SUM beds as total
cur = conn.execute("""
    SELECT FLOORPLAN_KEY, FLOORPLAN_CODE, SUM(BEDS) AS TOTAL_BEDS
    FROM dbo.FORECAST_BUDGET_TIERS
    WHERE PROPERTY_KEY = 1069 AND AY = 2026 AND TIER_NUMBER <> 0
    GROUP BY FLOORPLAN_KEY, FLOORPLAN_CODE
    ORDER BY FLOORPLAN_CODE
""")
cols = [d[0] for d in cur.description]
print("Budget tiers floorplans:")
for r in cur.fetchall():
    print(dict(zip(cols, r)))

# Option 2: check FORECAST_FORECASTS for floorplan columns
cur2 = conn.execute("SELECT TOP 1 * FROM dbo.FORECAST_FORECASTS WHERE PROPERTY_KEY = 1069")
cols2 = [d[0] for d in cur2.description]
print("\nFORECAST_FORECASTS cols:", cols2)

conn.close()
