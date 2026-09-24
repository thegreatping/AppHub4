"""Find the real data for Pitch and Vendor Setup."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import load_env, SafeConnection

env  = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

print("=== THE_PITCH row count & columns ===")
cnt = conn.scalar("SELECT COUNT(*) FROM dbo.THE_PITCH")
print(f"  {cnt} rows")
cur = conn.execute("SELECT TOP 3 * FROM dbo.THE_PITCH ORDER BY ID DESC")
cols = [d[0] for d in cur.description]
print("  Cols:", cols)
for row in cur.fetchall():
    d = dict(zip(cols, row))
    for k, v in d.items():
        val = str(v)[:80] if v is not None else None
        print(f"    {k}: {val}")
    print()

print("\n=== Tables with 'pitch' in name ===")
for r in conn.fetchall("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE LOWER(TABLE_NAME) LIKE '%pitch%'"):
    print(" ", r[0])

print("\n=== Tables app_id=17 (Vendor Setup) might write to - all tables ===")
for r in conn.fetchall("""
    SELECT TABLE_NAME, (SELECT SUM(row_count) FROM sys.dm_db_partition_stats p
     WHERE p.object_id = OBJECT_ID('dbo.' + t.TABLE_NAME) AND p.index_id IN (0,1)) as approx_rows
    FROM INFORMATION_SCHEMA.TABLES t
    WHERE TABLE_SCHEMA='dbo'
      AND (LOWER(TABLE_NAME) LIKE '%vendor%' OR LOWER(TABLE_NAME) LIKE '%setup%' OR LOWER(TABLE_NAME) LIKE '%request%' OR LOWER(TABLE_NAME) LIKE '%onboard%')
    ORDER BY TABLE_NAME
"""):
    print(f"  {r[0]:40s}  rows~{r[1]}")
