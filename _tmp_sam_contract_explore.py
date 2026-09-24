"""Explore DB_APP_SUPPORT for SAM Contract Manager tables and schema."""
import sys
sys.path.insert(0, ".")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Find all SAM-related tables
print("=== SAM tables ===")
rows = conn.fetchall("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_TYPE='BASE TABLE' AND TABLE_NAME LIKE '%SAM%'
    ORDER BY TABLE_NAME
""")
for r in rows: print(" ", r[0])

print("\n=== APP_LIST row for SAM Contract Manager ===")
rows = conn.fetchall("SELECT App_ID, App_Name, Flag_Active FROM dbo.APP_LIST WHERE App_ID IN (10,11)")
for r in rows: print(f"  {r[0]} | {r[1]} | active={r[2]}")

# Check if there's a contract-related table
print("\n=== CONTRACT tables ===")
rows = conn.fetchall("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_TYPE='BASE TABLE' AND TABLE_NAME LIKE '%CONTRACT%'
    ORDER BY TABLE_NAME
""")
for r in rows: print(" ", r[0])
