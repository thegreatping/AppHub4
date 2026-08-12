import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection
env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Show all active rows for subjectID 3888 (48 WEST)
rows = conn.execute("""
    SELECT marketCompMapID, subjectID, compID, orderID, startCompDate, endCompDate, modifiedBy, modifiedDate
    FROM dbo.MktSrv_CompMap
    WHERE subjectID = 3888 AND endCompDate > GETDATE()
    ORDER BY orderID
""").fetchall()
print(f"Active rows for subjectID 3888: {len(rows)}")
for r in rows:
    print(r)
