import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Help Ticket Triage', 'bi-triage-agent', 'scripts'))
from helpers import SafeConnection, load_env

env = load_env()

# Connect same way as EDM does
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Check what database we're actually connected to
db_info = conn.fetchall("SELECT DB_NAME() AS db, @@SERVERNAME AS srv")
print(f"Connected to: {db_info[0][0]} on {db_info[0][1]}")

# Search for the table
rows = conn.fetchall("""
    SELECT TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME LIKE '%TITLE%' OR TABLE_NAME LIKE '%EMP%MGMT%'
    ORDER BY TABLE_NAME
""")
print(f"\nTables matching TITLE or EMP*MGMT:")
for r in rows:
    print(f"  {r[0]}.{r[1]}.{r[2]}")

conn.close()
