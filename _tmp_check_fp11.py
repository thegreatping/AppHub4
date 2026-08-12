import sys
sys.path.insert(0, '../Help Ticket Triage/bi-triage-agent/scripts')
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, 'DB_APP_SUPPORT', None, direct=True)

# Does FLOORPLAN_WORKSPACE.FLOORPLAN_ASSIGNMENT_KEY = FORECAST_BUDGET_TIERS.FLOORPLAN_KEY?
cur = conn.execute("""
    SELECT w.FLOORPLAN_ASSIGNMENT_KEY, w.FLOORPLAN_NAME, w.PROPERTY_KEY, w.BED_COUNT
    FROM dbo.FLOORPLAN_WORKSPACE w
    WHERE w.FLOORPLAN_ASSIGNMENT_KEY IN (189288, 189260, 189261, 189287, 189250)
""")
cols = [d[0] for d in cur.description]
print("FLOORPLAN_WORKSPACE by FLOORPLAN_ASSIGNMENT_KEY (= FLOORPLAN_KEY from budget tiers):")
for r in cur.fetchall():
    print(dict(zip(cols, r)))

# Also try FORECAST_BUDGET_TIERS.BED_TOTAL for total beds
cur2 = conn.execute("""
    SELECT DISTINCT FLOORPLAN_KEY, FLOORPLAN_CODE, BED_TOTAL
    FROM dbo.FORECAST_BUDGET_TIERS
    WHERE PROPERTY_KEY = 1069 AND AY = 2026 AND LEASE_TYPE = 'RENEWAL' AND TIER_NUMBER = 1
    ORDER BY FLOORPLAN_CODE
""")
cols2 = [d[0] for d in cur2.description]
print("\nBED_TOTAL from budget tiers tier 1:")
for r in cur2.fetchall():
    print(dict(zip(cols2, r)))

conn.close()
