import sys
sys.path.insert(0, '../Help Ticket Triage/bi-triage-agent/scripts')
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, 'DB_APP_SUPPORT', None, direct=True)
# Check what FORECAST_BUDGET_TIERS has for floorplan info
cur = conn.execute("""
    SELECT DISTINCT FLOORPLAN_KEY, FLOORPLAN_CODE, BEDS
    FROM dbo.FORECAST_BUDGET_TIERS
    WHERE PROPERTY_KEY = 1069 AND AY = 2026
    ORDER BY FLOORPLAN_CODE
""")
cols = [d[0] for d in cur.description]
for r in cur.fetchall():
    print(dict(zip(cols, r)))
conn.close()
