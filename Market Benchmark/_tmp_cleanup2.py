import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection
env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Delete all the MRB-App test garbage (NULL marketCompMapID = our broken inserts)
result = conn.execute("""
    DELETE FROM dbo.MktSrv_CompMap
    WHERE subjectID = 3888
      AND marketCompMapID IS NULL
      AND modifiedBy = 'MRB-App'
""")
conn.commit()
print("Deleted test rows")

# Confirm what's left
rows = conn.execute("""
    SELECT marketCompMapID, compID, orderID, endCompDate
    FROM dbo.MktSrv_CompMap
    WHERE subjectID = 3888 AND endCompDate > GETDATE()
    ORDER BY orderID
""").fetchall()
print(f"Remaining active rows: {len(rows)}")
for r in rows:
    print(r)

# Check max marketCompMapID so we know next value
mx = conn.execute("SELECT MAX(marketCompMapID) FROM dbo.MktSrv_CompMap").fetchone()
print(f"\nMax marketCompMapID: {mx[0]}")
