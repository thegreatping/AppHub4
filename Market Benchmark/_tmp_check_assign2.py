import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import SafeConnection, load_env
env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Find comp-map / master assignment tables
rows = conn.execute("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME LIKE '%COMP%' OR TABLE_NAME LIKE '%MAP%' OR TABLE_NAME LIKE '%ASSIGN%'
    ORDER BY TABLE_NAME
""").fetchall()
print("=== COMP/MAP/ASSIGN TABLES ===")
for r in rows:
    print(f"  {r[0]}")

# Check if any rows have non-null parent_property_key
rows = conn.execute("""
    SELECT COUNT(*) FROM COMP_ASSIGNMENTS WHERE PARENT_PROPERTY_KEY IS NOT NULL
""").fetchall()
print(f"\nRows with non-null parent_property_key: {rows[0][0]}")

# Check SUBJECTID vs RANK_ORDER - does subjectid map to a parent?
rows = conn.execute("""
    SELECT TOP 5 SUBJECTID, PARENT_PROPERTY_KEY, PARENT_PROPERTY_NAME, RANK_ORDER,
           COMP_PROPERTY_KEY, COMP_PROPERTY_NAME, DATE_KEY, STARTCOMPDATE, ENDCOMPDATE
    FROM COMP_ASSIGNMENTS
    WHERE DATE_KEY = 20260726
    ORDER BY SUBJECTID, RANK_ORDER
""").fetchall()
print("\n=== SAMPLE WITH SUBJECTID ===")
for r in rows:
    print(f"  {r}")

# Check distinct SUBJECTID values
rows = conn.execute("SELECT COUNT(DISTINCT SUBJECTID) FROM COMP_ASSIGNMENTS").fetchall()
print(f"\nDistinct SUBJECTID: {rows[0][0]}")

# Check PARENT_PROPERTY table - does it have a list of properties?
rows = conn.execute("SELECT TOP 5 PROPERTY_KEY, PROPERTY_NAME FROM PARENT_PROPERTY ORDER BY PROPERTY_NAME").fetchall()
print("\n=== SAMPLE PARENT_PROPERTY ===")
for r in rows:
    print(f"  {r}")

rows = conn.execute("SELECT COUNT(*) FROM PARENT_PROPERTY").fetchall()
print(f"Total parent properties: {rows[0][0]}")

conn.close()
