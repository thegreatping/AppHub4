import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection
env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Cross-reference subjectID with COMP_ASSIGNMENT_FACT to find PARENT_PROPERTY_KEY
rows = conn.execute("""
    SELECT DISTINCT TOP 10
        caf.SUBJECTID,
        caf.PARENT_PROPERTY_KEY,
        caf.PARENT_PROPERTY_NAME
    FROM dbo.COMP_ASSIGNMENT_FACT caf
    WHERE caf.SUBJECTID IN (25,27,28,29,30,31,32,33)
    ORDER BY caf.SUBJECTID
""").fetchall()
print("subjectID -> PARENT_PROPERTY_KEY via COMP_ASSIGNMENT_FACT:")
for r in rows:
    print(r)
