import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection
env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
# Check a known parent key
rows = conn.execute("""
    SELECT TOP 5 m.marketCompMapID, m.subjectID, m.compID, m.orderID,
           m.startCompDate, m.endCompDate, cp.PROPERTY_NAME
    FROM dbo.MktSrv_CompMap m
    JOIN dbo.COMP_PROPERTY cp ON cp.PROPERTY_KEY = m.compID
    WHERE m.endCompDate > GETDATE()
    ORDER BY m.subjectID, m.orderID
""").fetchall()
for r in rows:
    print(r)
