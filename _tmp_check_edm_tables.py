import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Help Ticket Triage', 'bi-triage-agent', 'scripts'))
from helpers import SafeConnection, load_env

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

tables = conn.fetchall("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'dbo'
    ORDER BY TABLE_NAME
""")
print("Tables in DB_APP_SUPPORT:")
for r in tables:
    print(f"  {r[0]}")

# Check specifically for EDM tables
edm_tables = ['EMP_TITLE_GROUP_MGMT', 'EMP_ENTRATA_TITLE_GROUP_MAPPING', 'EMP_SOFT_TERMINATIONS']
for t in edm_tables:
    exists = any(r[0] == t for r in tables)
    print(f"\n{t}: {'EXISTS' if exists else 'MISSING'}")

conn.close()
