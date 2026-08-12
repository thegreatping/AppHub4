import sys
sys.path.insert(0, '../Help Ticket Triage/bi-triage-agent/scripts')
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, 'DB_APP_SUPPORT', None, direct=True)
# Check FLOORPLAN_FACT columns
cur = conn.execute("SELECT TOP 3 * FROM dbo.FLOORPLAN_FACT WHERE PROPERTY_KEY = 1069")
cols = [d[0] for d in cur.description]
print("FLOORPLAN_FACT cols:", cols)
for r in cur.fetchall():
    print(dict(zip(cols, r)))
conn.close()
