import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Search broader
cur = conn.execute("""
    SELECT TABLE_SCHEMA, TABLE_NAME 
    FROM INFORMATION_SCHEMA.TABLES 
    WHERE TABLE_NAME LIKE '%AWARD%' OR TABLE_NAME LIKE '%NOMINATION%'
    ORDER BY TABLE_NAME
""")
for r in cur.fetchall():
    print(f"{r[0]}.{r[1]}")
