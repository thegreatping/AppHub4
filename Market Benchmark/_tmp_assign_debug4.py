import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection
env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Check COMP_PROPERTY for small subjectIDs
rows = conn.execute("""
    SELECT PROPERTY_KEY, PROPERTY_NAME, FLAG_PARENT, FLAG_COMP, FLAG_ACTIVE
    FROM dbo.COMP_PROPERTY
    WHERE PROPERTY_KEY IN (-1,1,25,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43)
    ORDER BY PROPERTY_KEY
""").fetchall()
print("COMP_PROPERTY for subjectID values:")
for r in rows:
    print(r)

# Also check PROPERTY_0 for small keys
rows2 = conn.execute("""
    SELECT PROPERTY_KEY, PROPERTY_NAME FROM dbo.PROPERTY_0 WHERE PROPERTY_KEY < 100 ORDER BY PROPERTY_KEY
""").fetchall()
print("\nPROPERTY_0 with small keys:", rows2)

# Check if MktSrv_CompMap subjectID -> COMP_PROPERTY works
rows3 = conn.execute("""
    SELECT DISTINCT TOP 5 m.subjectID, cp.PROPERTY_NAME, cp.FLAG_PARENT
    FROM dbo.MktSrv_CompMap m
    JOIN dbo.COMP_PROPERTY cp ON cp.PROPERTY_KEY = m.subjectID
    WHERE m.endCompDate > GETDATE()
    ORDER BY m.subjectID
""").fetchall()
print("\nsubjectID -> COMP_PROPERTY join:", rows3)
