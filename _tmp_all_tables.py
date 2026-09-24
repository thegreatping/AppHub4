"""Audit all DB tables vs what each blueprint actually queries."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import load_env, SafeConnection

env  = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

print("=== ALL dbo tables with approximate row counts ===")
rows = conn.fetchall("""
    SELECT t.TABLE_NAME,
           p.row_count
    FROM INFORMATION_SCHEMA.TABLES t
    LEFT JOIN (
        SELECT OBJECT_NAME(object_id) as tname, SUM(row_count) as row_count
        FROM sys.dm_db_partition_stats
        WHERE index_id IN (0,1)
        GROUP BY OBJECT_NAME(object_id)
    ) p ON p.tname = t.TABLE_NAME
    WHERE t.TABLE_SCHEMA = 'dbo'
    ORDER BY COALESCE(p.row_count,0) DESC, t.TABLE_NAME
""")
for r in rows:
    print(f"  {r[0]:50s}  ~{r[1]}")
