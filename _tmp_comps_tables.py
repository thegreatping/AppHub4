import sys
sys.path.insert(0, '../Help Ticket Triage/bi-triage-agent/scripts')
from helpers import load_env, SafeConnection
env = load_env()
conn = SafeConnection(env, 'DB_APP_SUPPORT', None, direct=True)

# Find comps/costar/market tables
cur = conn.execute("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_TYPE='BASE TABLE'
      AND (TABLE_NAME LIKE '%COMP%' OR TABLE_NAME LIKE '%COSTAR%'
           OR TABLE_NAME LIKE '%MARKET%' OR TABLE_NAME LIKE '%COMPET%')
    ORDER BY TABLE_NAME
""")
print("Candidate tables:")
for r in cur.fetchall():
    print(r[0])
conn.close()
