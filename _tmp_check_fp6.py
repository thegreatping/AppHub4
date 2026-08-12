import sys
sys.path.insert(0, '../Help Ticket Triage/bi-triage-agent/scripts')
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, 'DB_APP_SUPPORT', None, direct=True)

# Check FLOORPLAN_ACTUALS_RENT for friendly names
cur = conn.execute("""
    SELECT DISTINCT FLOORPLAN_KEY, FLOORPLAN_CODE
    FROM dbo.FLOORPLAN_ACTUALS_RENT
    WHERE PROPERTY_KEY = 1069 AND AY = 2026
    ORDER BY FLOORPLAN_CODE
""")
cols = [d[0] for d in cur.description]
print("FLOORPLAN_ACTUALS_RENT:")
for r in cur.fetchall():
    print(dict(zip(cols, r)))

# Also check FORECAST_BUDGET_TIERS for property 9797 to compare
cur2 = conn.execute("""
    SELECT DISTINCT FLOORPLAN_KEY, FLOORPLAN_CODE
    FROM dbo.FORECAST_BUDGET_TIERS
    WHERE PROPERTY_KEY = 9797 AND AY = 2026
    ORDER BY FLOORPLAN_CODE
""")
cols2 = [d[0] for d in cur2.description]
print("\nFORECAST_BUDGET_TIERS for 9797:")
for r in cur2.fetchall():
    print(dict(zip(cols2, r)))

conn.close()
