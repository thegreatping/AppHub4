"""Explore DB_APP_SUPPORT for Pitch Workflow tables."""
import sys
sys.path.insert(0, ".")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

print("=== PITCH / IDEA tables ===")
rows = conn.fetchall("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_TYPE='BASE TABLE'
      AND (TABLE_NAME LIKE '%PITCH%' OR TABLE_NAME LIKE '%IDEA%' OR TABLE_NAME LIKE '%WORKFLOW%')
    ORDER BY TABLE_NAME
""")
for r in rows: print(" ", r[0])

print("\n=== APP_LIST row ===")
rows = conn.fetchall("SELECT App_ID, App_Name, Flag_Active FROM dbo.APP_LIST WHERE App_Name LIKE '%Pitch%'")
for r in rows: print(f"  {r[0]} | {r[1]} | active={r[2]}")
