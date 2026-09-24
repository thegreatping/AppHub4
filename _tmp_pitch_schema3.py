"""Explore etransactions workflow tables and their relation to THE_PITCH."""
import sys
sys.path.insert(0, ".")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

for tbl in ["WorkflowAssignment", "WorkflowEvent"]:
    print(f"\n=== etransactions.{tbl} ===")
    rows = conn.fetchall(f"""
        SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA='etransactions' AND TABLE_NAME='{tbl}' ORDER BY ORDINAL_POSITION
    """)
    for r in rows: print(f"  {r[0]:40s} {r[1]:20s} len={r[2]}  null={r[3]}")
    cnt = conn.fetchall(f"SELECT COUNT(*) FROM etransactions.[{tbl}]")[0][0]
    print(f"  --> {cnt} rows")

print("\n=== All etransactions tables ===")
rows = conn.fetchall("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='etransactions' ORDER BY TABLE_NAME")
for r in rows: print(f"  {r[0]}")

print("\n=== Sample WorkflowEvent ===")
rows = conn.fetchall("SELECT TOP 3 * FROM etransactions.WorkflowEvent ORDER BY 1 DESC")
cols = [r[0] for r in conn.fetchall("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='etransactions' AND TABLE_NAME='WorkflowEvent' ORDER BY ORDINAL_POSITION")]
for row in rows:
    for i, v in enumerate(row): print(f"  {cols[i]}: {v}")
    print()
