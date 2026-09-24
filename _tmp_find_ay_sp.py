import sys, os
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, 'DB_APP_SUPPORT', None, direct=True)

print("=== Searching for AY / Cutover SPs ===")
rows = conn.fetchall("""
    SELECT ROUTINE_SCHEMA, ROUTINE_NAME
    FROM INFORMATION_SCHEMA.ROUTINES
    WHERE ROUTINE_TYPE = 'PROCEDURE'
      AND (
           ROUTINE_NAME LIKE '%AY%'
        OR ROUTINE_NAME LIKE '%Cutover%'
        OR ROUTINE_NAME LIKE '%cutover%'
        OR ROUTINE_NAME LIKE '%ActionFlow%'
        OR ROUTINE_NAME LIKE '%Academic%'
      )
    ORDER BY ROUTINE_NAME
""")
if not rows:
    print("(no matches)")
else:
    for r in rows:
        print(f"  {r[0]}.{r[1]}")
