import sys
sys.path.insert(0, '../Help Ticket Triage/bi-triage-agent/scripts')
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, 'DB_APP_SUPPORT', None, direct=True)

# Does FLOORPLAN_ASSIGNMENTS.FLOORPLAN_ASSIGNMENT_KEY match FORECAST_BUDGET_TIERS.FLOORPLAN_KEY?
keys = [189260, 189261, 189287, 189250, 189265, 189251, 189252, 189256, 189267, 189257, 189264]
placeholders = ','.join(['?']*len(keys))

cur = conn.execute(f"""
    SELECT FLOORPLAN_ASSIGNMENT_KEY, FLOORPLAN_NAME, BED_COUNT, PROPERTY_KEY
    FROM dbo.FLOORPLAN_ASSIGNMENTS
    WHERE FLOORPLAN_ASSIGNMENT_KEY IN ({placeholders})
""", keys)
rows = cur.fetchall()
print(f"FLOORPLAN_ASSIGNMENTS match ({len(rows)} rows):")
for r in rows:
    print(r)

# Also check REVMGMT_FLOORPLANS without property filter - see if keys match
print()
cur2 = conn.execute(f"""
    SELECT FLOORPLAN_KEY, FLOORPLAN_NAME, PROPERTY_KEY, FLOORPLAN_BEDCOUNT
    FROM dbo.REVMGMT_FLOORPLANS
    WHERE FLOORPLAN_KEY IN ({placeholders})
""", keys)
rows2 = cur2.fetchall()
print(f"REVMGMT_FLOORPLANS match ({len(rows2)} rows):")
for r in rows2:
    print(r)

conn.close()
