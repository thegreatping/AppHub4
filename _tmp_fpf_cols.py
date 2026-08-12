import sys
sys.path.insert(0, '../Help Ticket Triage/bi-triage-agent/scripts')
from helpers import load_env, SafeConnection
env = load_env()

# Check FLOORPLANS_F columns in WH_STAGING
conn = SafeConnection(env, 'WH_STAGING', None, direct=True)
cur = conn.execute("SELECT TOP 1 * FROM dbo.FLOORPLANS_F WHERE PROPERTY_KEY=1069")
cols = [d[0] for d in cur.description]
print("FLOORPLANS_F cols:", cols)
row = cur.fetchone()
print("sample:", dict(zip(cols, row)))
conn.close()
