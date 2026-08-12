import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Find the table
cur = conn.execute("""
    SELECT TABLE_SCHEMA, TABLE_NAME 
    FROM INFORMATION_SCHEMA.TABLES 
    WHERE TABLE_NAME LIKE '%MINDSET%'
""")
tables = cur.fetchall()
print("Tables:", tables)

if tables:
    schema, tbl = tables[0]
    cur2 = conn.execute(f"""
        SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{tbl}'
        ORDER BY ORDINAL_POSITION
    """)
    print(f"\nColumns for {schema}.{tbl}:")
    for r in cur2.fetchall():
        print(f"  {r[0]} ({r[1]}, {r[2]})")

    # Sample data
    cur3 = conn.execute(f"SELECT TOP 3 * FROM [{schema}].[{tbl}]")
    cols = [d[0] for d in cur3.description]
    print(f"\nSample rows ({cols}):")
    for row in cur3.fetchall():
        print(f"  {list(row)}")
    
    # Count
    cur4 = conn.execute(f"SELECT COUNT(*) FROM [{schema}].[{tbl}]")
    print(f"\nTotal rows: {cur4.fetchone()[0]}")
