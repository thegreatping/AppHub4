import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection
env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Test _get_subject_id for 48 WEST (key=9797)
row = conn.execute("""
    SELECT TOP 1 SUBJECTID
    FROM dbo.COMP_ASSIGNMENTS
    WHERE PARENT_PROPERTY_KEY = 9797 AND SUBJECTID IS NOT NULL
    ORDER BY DATE_KEY DESC
""").fetchone()
print("SUBJECTID for 48 WEST (9797):", row)

# Also check what COMP_ASSIGNMENTS looks like for 48 WEST latest week
rows = conn.execute("""
    SELECT TOP 3 DATE_KEY, COMP_PROPERTY_KEY, COMP_PROPERTY_NAME, RANK_ORDER, MARKETCOMPMAPID, SUBJECTID, FLAG_COMP, FLAG_PARENT
    FROM dbo.COMP_ASSIGNMENTS
    WHERE PARENT_PROPERTY_KEY = 9797
    ORDER BY DATE_KEY DESC, RANK_ORDER
""").fetchall()
for r in rows:
    print(r)
