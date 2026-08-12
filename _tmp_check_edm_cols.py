import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Help Ticket Triage', 'bi-triage-agent', 'scripts'))
from helpers import SafeConnection, load_env

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

for tbl in ['EMPLOYEE_TITLE_CONTROL_0', 'EMPLOYEE_TITLES_0', 'EMPLOYEE_TITLE_GROUPS_0', 'EMPLOYEE_TITLE_GROUP_LEVELS_0', 'EMP_ENTRATA_GROUP_ASSIGNMENTS_0', 'EMPLOYEE_SOFT_TERMINATIONS']:
    try:
        cols = conn.fetchall(f"SELECT TOP 0 * FROM dbo.{tbl}")
        desc = conn._conn.cursor().execute(f"SELECT TOP 1 * FROM dbo.{tbl}").description
        print(f"\n{tbl}: {[d[0] for d in desc]}")
        row = conn.fetchone(f"SELECT TOP 1 * FROM dbo.{tbl}")
        if row:
            print(f"  sample: {row}")
        else:
            print(f"  (empty)")
    except Exception as e:
        print(f"\n{tbl}: ERROR - {e}")

conn.close()
