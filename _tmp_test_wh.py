import sys
sys.path.insert(0, '../Help Ticket Triage/bi-triage-agent/scripts')
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, 'WH_STAGING', None, direct=True)
cur = conn.execute("""
    SELECT TOP 3 FLOORPLAN_KEY, FLOORPLAN AS FLOORPLAN_NAME, BEDS
    FROM dbo.FLOORPLANS_F
    WHERE PROPERTY_KEY = 1069 AND FLAG_REPORTABLE = 1
    ORDER BY FLOORPLAN
""")
for r in cur.fetchall():
    print(r)
conn.close()
print("WH_STAGING connection works!")
