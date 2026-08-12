import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection
env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# See which subjectIDs in CompMap match PROPERTY_0
rows = conn.execute("""
    SELECT TOP 10 m.subjectID, p.PROPERTY_KEY, p.PROPERTY_NAME, COUNT(*) as cnt
    FROM dbo.MktSrv_CompMap m
    JOIN dbo.PROPERTY_0 p ON p.PROPERTY_KEY = m.subjectID
    WHERE m.endCompDate > GETDATE()
      AND p.FLAG_REPORTABLE = 1 AND p.FLAG_DISPOSITIONED = 0
    GROUP BY m.subjectID, p.PROPERTY_KEY, p.PROPERTY_NAME
    ORDER BY cnt DESC
""").fetchall()
print("subjectIDs that match PROPERTY_0 dropdown:")
for r in rows:
    print(r)

# Also check a parent that's in dropdown but may not be in CompMap
rows2 = conn.execute("""
    SELECT TOP 5 PROPERTY_KEY, PROPERTY_NAME FROM dbo.PROPERTY_0
    WHERE FLAG_REPORTABLE=1 AND FLAG_DISPOSITIONED=0
    ORDER BY PROPERTY_NAME
""").fetchall()
print("\nFirst 5 properties in dropdown:")
for r in rows2:
    print(r)
