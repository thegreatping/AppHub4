"""Final: name join test and Z_WeekList."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Z_WeekList
print("=== Adaptive_Z_WeekList ===")
cur = conn.execute("SELECT TOP 0 * FROM dbo.Adaptive_Z_WeekList")
cols = [d[0] for d in cur.description]
print("  Cols:", cols)
cur2 = conn.execute("SELECT TOP 10 * FROM dbo.Adaptive_Z_WeekList ORDER BY 1 DESC")
for r in cur2.fetchall():
    print("  ", dict(zip(cols, r)))

# Test direct PROPERTY_NAME join - exact match after extracting suffix from Levels
# "102 48 West" -> "48 West" -> vs "48 WEST" (uppercase)
print("\n=== Test name join ===")
cur3 = conn.execute("""
    SELECT t.Levels, p.PROPERTY_KEY, p.PROPERTY_NAME
    FROM dbo.Adaptive_Weekly_Tracker_Targets t
    JOIN dbo.PROPERTY_0 p
      ON p.PROPERTY_NAME = UPPER(LTRIM(SUBSTRING(t.Levels, CHARINDEX(' ', t.Levels)+1, 200)))
    WHERE t.Academic_Yr = '26-27 AY'
    GROUP BY t.Levels, p.PROPERTY_KEY, p.PROPERTY_NAME
    ORDER BY p.PROPERTY_NAME
""")
rows = cur3.fetchall()
print(f"  {len(rows)} matched properties")
for r in rows[:10]:
    print(f"  '{r[0]}' -> KEY={r[1]}, '{r[2]}'")

# Also test ACADEMIC_YEAR_F
print("\n=== ACADEMIC_YEAR_F ===")
cur4 = conn.execute("SELECT TOP 0 * FROM dbo.ACADEMIC_YEAR_F")
cols4 = [d[0] for d in cur4.description]
print("  Cols:", cols4)
cur5 = conn.execute("SELECT TOP 5 * FROM dbo.ACADEMIC_YEAR_F ORDER BY 1 DESC")
for r in cur5.fetchall():
    print("  ", dict(zip(cols4, r)))

conn.close()
