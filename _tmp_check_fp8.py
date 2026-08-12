import sys
sys.path.insert(0, '../Help Ticket Triage/bi-triage-agent/scripts')
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, 'DB_APP_SUPPORT', None, direct=True)

cur = conn.execute("""
    SELECT DISTINCT FLOORPLAN_KEY, FLOORPLAN_NAME, FLOORPLAN_BEDCOUNT
    FROM dbo.REVMGMT_FLOORPLANS
    WHERE PROPERTY_KEY = 1069
    ORDER BY FLOORPLAN_NAME
""")
cols = [d[0] for d in cur.description]
for r in cur.fetchall():
    print(dict(zip(cols, r)))
conn.close()
