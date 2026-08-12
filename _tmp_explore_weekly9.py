"""Check PROPERTY_0 columns and map Adaptive Levels to PROPERTY_KEY."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# PROPERTY_0 columns
print("=== PROPERTY_0 columns ===")
cur = conn.execute("SELECT TOP 0 * FROM dbo.PROPERTY_0")
print("  ", [d[0] for d in cur.description])

# 48 West and GeoCentral
cur2 = conn.execute("""
    SELECT PROPERTY_KEY, PROPERTY_NAME
    FROM dbo.PROPERTY_0
    WHERE PROPERTY_NAME LIKE '%48%WEST%' OR PROPERTY_NAME LIKE '%GEOCENTRAL%'
""")
for r in cur2.fetchall():
    print(f"  KEY={r[0]}, NAME={r[1]}")

# Adaptive - how the Levels prefix maps: "102 48 West" - does 102 = property key?
# Check if 102 is the PROPERTY_KEY for 48 West
cur3 = conn.execute("SELECT PROPERTY_KEY, PROPERTY_NAME FROM dbo.PROPERTY_0 WHERE PROPERTY_KEY IN (102, 170)")
for r in cur3.fetchall():
    print(f"  KEY={r[0]}, NAME={r[1]}")

# Check Adaptive weekly tracker for week range
print("\n=== 48 West budget weeks (26-27 AY) ===")
cur4 = conn.execute("""
    SELECT Week_Beginning,
           CAST(SUBSTRING(Week_Beginning, 2, 10) AS INT) as wk_num,
           Total_Weekly, New_Weekly, Renewal_Weekly
    FROM dbo.Adaptive_Weekly_Tracker_Targets
    WHERE Levels = '102 48 West' AND Academic_Yr = '26-27 AY'
    ORDER BY CAST(SUBSTRING(Week_Beginning, 2, 10) AS INT)
""")
rows = cur4.fetchall()
print(f"  {len(rows)} weeks")
for r in rows:
    print(f"  W{r[1]}: Total={r[2]:.0f} New={r[3]:.0f} Ren={r[4]:.0f}")

# PY1 from _2025 table
print("\n=== 48 West PY1 budget weeks (25-26 AY) ===")
cur5 = conn.execute("""
    SELECT Week_Beginning,
           CAST(SUBSTRING(Week_Beginning, 2, 10) AS INT) as wk_num,
           Total_Weekly, New_Weekly, Renewal_Weekly
    FROM dbo.Adaptive_Weekly_Tracker_Targets_2025
    WHERE Levels = '102 48 West' AND Academic_Yr = '25-26 AY'
    ORDER BY CAST(SUBSTRING(Week_Beginning, 2, 10) AS INT)
""")
rows2 = cur5.fetchall()
print(f"  {len(rows2)} weeks")
for r in rows2[:10]:
    print(f"  W{r[1]}: Total={r[2]:.0f} New={r[3]:.0f} Ren={r[4]:.0f}")

# Does the numeric prefix in Levels = some internal ID? Let's check
# The join attempt: "102 48 West" → PROPERTY_KEY=9797 (from earlier research)
# So the number is NOT the PROPERTY_KEY. Must be an Adaptive internal ID.
# We need a different join strategy: match property name substring
print("\n=== Test name-based join ===")
cur6 = conn.execute("""
    SELECT t.Levels, p.PROPERTY_KEY, p.PROPERTY_NAME
    FROM dbo.Adaptive_Weekly_Tracker_Targets t
    JOIN (SELECT DISTINCT PROPERTY_KEY, PROPERTY_NAME FROM dbo.PROPERTY_0) p
      ON p.PROPERTY_NAME = UPPER(LTRIM(SUBSTRING(t.Levels, CHARINDEX(' ', t.Levels)+1, 200)))
    WHERE t.Academic_Yr = '26-27 AY' AND (t.Levels LIKE '%48 West%' OR t.Levels LIKE '%GeoCentral%')
""")
for r in cur6.fetchall():
    print(f"  Levels='{r[0]}' -> KEY={r[1]}, NAME={r[2]}")

conn.close()
