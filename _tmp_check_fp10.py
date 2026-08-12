import sys
sys.path.insert(0, '../Help Ticket Triage/bi-triage-agent/scripts')
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, 'DB_APP_SUPPORT', None, direct=True)

# Check if FORECAST_BUDGET_TIERS has FLOORPLAN_ASSIGNMENT_KEY or links to it
cur = conn.execute("SELECT TOP 1 * FROM dbo.FORECAST_BUDGET_TIERS")
cols = [d[0] for d in cur.description]
print("FORECAST_BUDGET_TIERS cols:", cols)

# Check FLOORPLAN_ASSIGNMENTS for GEO CENTRAL property 1069
print()
cur2 = conn.execute("""
    SELECT FLOORPLAN_ASSIGNMENT_KEY, FLOORPLAN_NAME, BED_COUNT, PROPERTY_KEY
    FROM dbo.FLOORPLAN_ASSIGNMENTS
    WHERE PROPERTY_KEY = 1069 AND FLAG_ACTIVE = 1
    ORDER BY FLOORPLAN_NAME
""")
cols2 = [d[0] for d in cur2.description]
for r in cur2.fetchall():
    print(dict(zip(cols2, r)))

conn.close()
