import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Help Ticket Triage', 'bi-triage-agent', 'scripts'))
from helpers import SafeConnection, load_env
env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
r = conn.fetchall("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE '%SOFT_TERM%' OR TABLE_NAME LIKE '%OVERRIDES%'")
for x in r:
    print(f"{x[0]}.{x[1]}")
conn.close()
