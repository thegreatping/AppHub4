import sys
sys.path.insert(0, ".")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_BI_SUPPORT", None, direct=True)
try:
    cols = conn.fetchall("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA='control' AND TABLE_NAME='Execution_Plan'
        ORDER BY ORDINAL_POSITION
    """)
    print("COLUMNS:", [c[0] for c in cols])
    rows = conn.fetchall("SELECT TOP 5 * FROM control.Execution_Plan")
    print("SAMPLE:")
    for r in rows:
        print(r)
finally:
    conn.close()
