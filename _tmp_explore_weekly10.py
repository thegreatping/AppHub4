"""Final data check: AY dates and name-join for Adaptive tables."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# ACADEMIC_YEARS_LOCAL
print("=== ACADEMIC_YEARS_LOCAL ===")
cur = conn.execute("SELECT TOP 0 * FROM dbo.ACADEMIC_YEARS_LOCAL")
print("  ", [d[0] for d in cur.description])
cur2 = conn.execute("SELECT * FROM dbo.ACADEMIC_YEARS_LOCAL ORDER BY 1 DESC")
for r in cur2.fetchall():
    print("  ", r)

# Test name join
print("\n=== Adaptive name join test ===")
cur3 = conn.execute("""
    SELECT t.Levels, p.PROPERTY_KEY, p.PROPERTY_NAME
    FROM dbo.Adaptive_Weekly_Tracker_Targets t
    JOIN (SELECT DISTINCT PROPERTY_KEY, PROPERTY_NAME FROM dbo.PROPERTY_0) p
      ON UPPER(LTRIM(SUBSTRING(t.Levels, CHARINDEX(' ', t.Levels)+1, 200))) LIKE '%' + p.PROPERTY_NAME + '%'
         OR p.PROPERTY_NAME LIKE '%' + UPPER(LTRIM(SUBSTRING(t.Levels, CHARINDEX(' ', t.Levels)+1, 200))) + '%'
    WHERE t.Academic_Yr = '26-27 AY' AND (t.Levels LIKE '%48 West%' OR t.Levels LIKE '%GeoCentral%')
    GROUP BY t.Levels, p.PROPERTY_KEY, p.PROPERTY_NAME
""")
for r in cur3.fetchall():
    print(f"  Levels='{r[0]}' -> KEY={r[1]}, NAME={r[2]}")

# Check Z_WeekList for AY week start dates
print("\n=== Adaptive_Z_WeekList columns ===")
cur4 = conn.execute("SELECT TOP 0 * FROM dbo.Adaptive_Z_WeekList")
cols = [d[0] for d in cur4.description]
print("  ", cols)
cur5 = conn.execute("SELECT TOP 5 * FROM dbo.Adaptive_Z_WeekList ORDER BY 1 DESC")
for r in cur5.fetchall():
    print("  ", dict(zip(cols, r)))

conn.close()
