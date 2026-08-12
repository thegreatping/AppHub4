import sys
sys.path.insert(0, '../Help Ticket Triage/bi-triage-agent/scripts')
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, 'DB_APP_SUPPORT', None, direct=True)
cur = conn.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE '%FLOOR%' OR TABLE_NAME LIKE '%PLAN%' ORDER BY TABLE_NAME")
for r in cur.fetchall():
    print(r[0])
conn.close()
