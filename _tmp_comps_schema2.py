import sys
sys.path.insert(0, '../Help Ticket Triage/bi-triage-agent/scripts')
from helpers import load_env, SafeConnection
env = load_env()
conn = SafeConnection(env, 'DB_APP_SUPPORT', None, direct=True)

for tbl in ['FORECAST_COMP_LIST', 'FORECAST_COMP_FLOORPLANS', 'FORECAST_COMP_FLOORPLANS_BASE']:
    cur = conn.execute(f"SELECT TOP 1 * FROM dbo.{tbl}")
    cols = [d[0] for d in cur.description]
    print(f"\n{tbl} cols:\n  {cols}")
    row = cur.fetchone()
    if row:
        print(f"  sample: {dict(zip(cols, row))}")

conn.close()
