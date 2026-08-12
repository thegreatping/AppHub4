import sys
sys.path.insert(0, '../Help Ticket Triage/bi-triage-agent/scripts')
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, 'DB_APP_SUPPORT', None, direct=True)

# Check REVMGMT_FLOORPLANS
cur = conn.execute("SELECT TOP 3 * FROM dbo.REVMGMT_FLOORPLANS WHERE PROPERTY_KEY = 1069")
cols = [d[0] for d in cur.description]
print("REVMGMT_FLOORPLANS cols:", cols)
for r in cur.fetchall():
    print({k: v for k, v in zip(cols, r) if 'KEY' in k or 'NAME' in k or 'FLOOR' in k or 'CODE' in k})

# Check MktSrv_FloorPlanList
cur2 = conn.execute("SELECT TOP 3 * FROM dbo.MktSrv_FloorPlanList WHERE PROPERTY_KEY = 1069")
cols2 = [d[0] for d in cur2.description]
print("\nMktSrv_FloorPlanList cols:", cols2)
for r in cur2.fetchall():
    print({k: v for k, v in zip(cols2, r) if 'KEY' in k or 'NAME' in k or 'FLOOR' in k or 'CODE' in k})

conn.close()
