"""Find actual schema for WorkflowAssignment and WorkflowEvent."""
import sys
sys.path.insert(0, ".")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Find their actual schema
for tbl in ["WorkflowAssignment", "WorkflowEvent"]:
    rows = conn.fetchall(f"""
        SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_NAME = '{tbl}'
    """)
    for r in rows: print(f"  schema={r[0]}  table={r[1]}")

# THE_PITCH has 0 rows — need to understand what fields it has and what the
# Power Apps version actually stores. Check if there's a PITCH_ prefixed table we missed.
print("\n=== All tables containing PITCH or IDEA (any schema) ===")
rows = conn.fetchall("""
    SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME LIKE '%PITCH%' OR TABLE_NAME LIKE '%IDEA%'
    ORDER BY TABLE_SCHEMA, TABLE_NAME
""")
for r in rows: print(f"  [{r[0]}].{r[1]}")

print("\n=== THE_PITCH columns + sample ===")
rows = conn.fetchall("""
    SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
    FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='THE_PITCH' ORDER BY ORDINAL_POSITION
""")
for r in rows: print(f"  {r[0]:40s} {r[1]} len={r[2]}")
