import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Check for new hire tables
cur = conn.execute("""
    SELECT TABLE_SCHEMA, TABLE_NAME 
    FROM INFORMATION_SCHEMA.TABLES 
    WHERE TABLE_NAME LIKE '%NEW_HIRE%' OR TABLE_NAME LIKE '%NEWHIRE%' OR TABLE_NAME LIKE '%HIRE_ALERT%'
    ORDER BY TABLE_NAME
""")
tables = cur.fetchall()
print("Tables found:")
for t in tables:
    print(f"  {t[0]}.{t[1]}")

# Check if there's anything in APP_ADMINS for this app
cur2 = conn.execute("SELECT * FROM dbo.APP_ADMINS WHERE APP_ID = 16")
admins = cur2.fetchall()
print(f"\nAdmins for APP_ID=16: {len(admins)}")
for a in admins:
    print(f"  {a}")

# Also check what columns exist if tables found
for schema, tbl in tables:
    cur3 = conn.execute(f"""
        SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{tbl}'
        ORDER BY ORDINAL_POSITION
    """)
    print(f"\nColumns for {schema}.{tbl}:")
    for r in cur3.fetchall():
        print(f"  {r[0]} ({r[1]}, {r[2]})")
    
    cur4 = conn.execute(f"SELECT COUNT(*) FROM [{schema}].[{tbl}]")
    print(f"  Row count: {cur4.fetchone()[0]}")
    
    cur5 = conn.execute(f"SELECT TOP 3 * FROM [{schema}].[{tbl}]")
    cols = [d[0] for d in cur5.description]
    print(f"  Columns: {cols}")
    for row in cur5.fetchall():
        print(f"  {list(row)}")
