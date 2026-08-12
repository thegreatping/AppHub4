import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Help Ticket Triage', 'bi-triage-agent', 'scripts'))
from helpers import SafeConnection, load_env
env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
r = conn.fetchall("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'EMPLOYEE_SOFT_TERMINATION_OVERRIDES_STG' ORDER BY ORDINAL_POSITION")
print("EMPLOYEE_SOFT_TERMINATION_OVERRIDES_STG columns:")
for x in r:
    print(f"  {x[0]} ({x[1]})")
conn.close()
