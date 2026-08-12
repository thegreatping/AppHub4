import sys
sys.path.insert(0, '../Help Ticket Triage/bi-triage-agent/scripts')
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, 'DB_APP_SUPPORT', None, direct=True)
cur = conn.execute("SELECT TOP 3 * FROM dbo.FLOORPLAN_WORKSPACE WHERE PROPERTY_KEY = 1069")
cols = [d[0] for d in cur.description]
print("Cols:", [c for c in cols if 'KEY' in c or 'FLOOR' in c or 'BED' in c or 'REPORT' in c or 'NAME' in c])
for r in cur.fetchall():
    row = dict(zip(cols, r))
    print({k: row[k] for k in cols if 'KEY' in k or 'FLOOR' in k or 'BED' in k or 'REPORT' in k or 'NAME' in k})
conn.close()
