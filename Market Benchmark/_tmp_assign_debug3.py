import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection
env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# What subjectIDs exist in CompMap?
rows = conn.execute("SELECT DISTINCT TOP 20 subjectID FROM dbo.MktSrv_CompMap WHERE endCompDate > GETDATE() ORDER BY subjectID").fetchall()
print("Active subjectIDs:", [r[0] for r in rows])

# Try PARENT_PROPERTY table
rows2 = conn.execute("SELECT TOP 10 PROPERTY_KEY, PROPERTY_NAME FROM dbo.PARENT_PROPERTY ORDER BY PROPERTY_NAME").fetchall()
print("\nPARENT_PROPERTY sample:", rows2)

# Try join to PARENT_PROPERTY
rows3 = conn.execute("""
    SELECT TOP 5 m.subjectID, pp.PROPERTY_KEY, pp.PROPERTY_NAME, COUNT(*) as cnt
    FROM dbo.MktSrv_CompMap m
    JOIN dbo.PARENT_PROPERTY pp ON pp.PROPERTY_KEY = m.subjectID
    WHERE m.endCompDate > GETDATE()
    GROUP BY m.subjectID, pp.PROPERTY_KEY, pp.PROPERTY_NAME
    ORDER BY cnt DESC
""").fetchall()
print("\nJoin to PARENT_PROPERTY:", rows3)
