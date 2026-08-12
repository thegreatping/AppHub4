import sys
sys.path.insert(0, '../Help Ticket Triage/bi-triage-agent/scripts')
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, 'DB_APP_SUPPORT', None, direct=True)

# Check what property keys are in REVMGMT_FLOORPLANS and match with FLOORPLAN_KEY=189288
cur = conn.execute("""
    SELECT DISTINCT PROPERTY_KEY, FLOORPLAN_KEY, FLOORPLAN_NAME, FLOORPLAN_BEDCOUNT
    FROM dbo.REVMGMT_FLOORPLANS
    WHERE FLOORPLAN_KEY IN (189288, 189260, 26537)
""")
cols = [d[0] for d in cur.description]
for r in cur.fetchall():
    print(dict(zip(cols, r)))

# Also check FLOORPLAN_ASSIGNMENTS which has both keys
print()
cur2 = conn.execute("SELECT TOP 1 * FROM dbo.FLOORPLAN_ASSIGNMENTS")
cols2 = [d[0] for d in cur2.description]
print("FLOORPLAN_ASSIGNMENTS cols:", cols2)

conn.close()
