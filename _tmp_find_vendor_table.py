"""Find existing vendor setup tables and inspect their schema."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import load_env, SafeConnection

env  = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

print("=== Tables with 'vendor' in name ===")
rows = conn.fetchall("""
    SELECT TABLE_SCHEMA, TABLE_NAME
    FROM INFORMATION_SCHEMA.TABLES
    WHERE LOWER(TABLE_NAME) LIKE '%vendor%'
    ORDER BY TABLE_NAME
""")
for r in rows:
    print(f"  {r[0]}.{r[1]}")

print("\n=== Tables with 'setup' in name ===")
rows = conn.fetchall("""
    SELECT TABLE_SCHEMA, TABLE_NAME
    FROM INFORMATION_SCHEMA.TABLES
    WHERE LOWER(TABLE_NAME) LIKE '%setup%'
    ORDER BY TABLE_NAME
""")
for r in rows:
    print(f"  {r[0]}.{r[1]}")

print("\n=== APP_LIST entries for vendor/setup (App_ID context) ===")
rows = conn.fetchall("""
    SELECT App_ID, App_Name FROM dbo.APP_LIST
    WHERE LOWER(App_Name) LIKE '%vendor%' OR LOWER(App_Name) LIKE '%setup%'
""")
for r in rows:
    print(f"  App_ID={r[0]}  {r[1]}")
