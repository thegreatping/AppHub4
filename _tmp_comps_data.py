import sys
sys.path.insert(0, '../Help Ticket Triage/bi-triage-agent/scripts')
from helpers import load_env, SafeConnection
env = load_env()
conn = SafeConnection(env, 'DB_APP_SUPPORT', None, direct=True)

# Get comps for GEO CENTRAL forecast 284
cur = conn.execute("""
    SELECT COMP_PROPERTY_NAME, COMPARE_AS_FLOORPLAN_TYPE,
           NER_PRELEASE_FURNISHED, FLAG_SOLD_OUT, FLAG_INCLUDE,
           FLOORPLAN_NAME, BED_COUNT
    FROM dbo.FORECAST_COMP_FLOORPLANS
    WHERE FORECAST_KEY = 284 AND PARENT_PROPERTY_KEY = 1069
    ORDER BY FLAG_INCLUDE DESC, COMP_PROPERTY_NAME, COMPARE_AS_FLOORPLAN_TYPE
""")
cols = [d[0] for d in cur.description]
rows = cur.fetchall()
print(f"{len(rows)} rows:")
for r in rows:
    print(dict(zip(cols, r)))

conn.close()
