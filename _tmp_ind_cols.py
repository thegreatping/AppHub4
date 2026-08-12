import sys
sys.path.insert(0, '../Help Ticket Triage/bi-triage-agent/scripts')
from helpers import load_env, SafeConnection
env = load_env()
conn = SafeConnection(env, 'DB_APP_SUPPORT', None, direct=True)
cur = conn.execute("SELECT TOP 1 * FROM dbo.FORECAST_BUDGET_INDUCEMENTS")
print([d[0] for d in cur.description])
conn.close()
