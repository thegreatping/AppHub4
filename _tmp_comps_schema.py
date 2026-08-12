import sys
sys.path.insert(0, '../Help Ticket Triage/bi-triage-agent/scripts')
from helpers import load_env, SafeConnection
env = load_env()
conn = SafeConnection(env, 'DB_APP_SUPPORT', None, direct=True)

# FORECAST_COMP_LIST schema + sample
cur = conn.execute("SELECT TOP 3 * FROM dbo.FORECAST_COMP_LIST WHERE PROPERTY_KEY=1069")
cols = [d[0] for d in cur.description]
print("FORECAST_COMP_LIST cols:", cols)
for r in cur.fetchall():
    print(dict(zip(cols, r)))

print()
# FORECAST_COMP_FLOORPLANS schema + sample
cur2 = conn.execute("SELECT TOP 3 * FROM dbo.FORECAST_COMP_FLOORPLANS WHERE PROPERTY_KEY=1069")
cols2 = [d[0] for d in cur2.description]
print("FORECAST_COMP_FLOORPLANS cols:", cols2)
for r in cur2.fetchall():
    print(dict(zip(cols2, r)))

conn.close()
