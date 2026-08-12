"""Final check: Adaptive_Z_WeeklyTracker and property name matching for weekly leasing."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# What academic years are in Z_WeeklyTracker?
print("=== Adaptive_Z_WeeklyTracker - distinct AY and counts ===")
cur = conn.execute("""
    SELECT Academic_Yr, COUNT(*) as cnt, COUNT(DISTINCT Level_Name) as props
    FROM dbo.Adaptive_Z_WeeklyTracker
    GROUP BY Academic_Yr ORDER BY Academic_Yr
""")
for r in cur.fetchall():
    print(f"  AY={r[0]}, rows={r[1]}, properties={r[2]}")

# Sample 48 West in Z_WeeklyTracker (any account)
print("\n=== Adaptive_Z_WeeklyTracker - 48 West ALL accounts ===")
cur = conn.execute("""
    SELECT TOP 20 Level_Name, Academic_Yr, Week_Beginning, Account_Name, Data_Value
    FROM dbo.Adaptive_Z_WeeklyTracker
    WHERE Level_Name LIKE '%48%West%' OR Level_Name LIKE '%48%WEST%'
    ORDER BY Academic_Yr DESC, Week_Beginning, Account_Name
""")
for r in cur.fetchall():
    print(f"  {r[0]} | AY={r[1]} | Wk={r[2]} | Acct={r[3]} | Val={r[4]}")

# What level names contain "Geo" or "geo"?
print("\n=== Adaptive_Z_WeeklyTracker - GeoCentral level names ===")
cur = conn.execute("""
    SELECT DISTINCT Level_Name, Academic_Yr FROM dbo.Adaptive_Z_WeeklyTracker
    WHERE Level_Name LIKE '%Geo%' ORDER BY Level_Name, Academic_Yr
""")
for r in cur.fetchall():
    print(f"  '{r[0]}' AY={r[1]}")

# Check Adaptive_Weekly_Tracker_Targets - how 'Levels' maps to property_key
print("\n=== Adaptive_Weekly_Tracker_Targets - join attempt with PROPERTY_0 ===")
cur = conn.execute("""
    SELECT TOP 5 t.Levels, p.PROPERTY_KEY, p.PROPERTY_NAME
    FROM dbo.Adaptive_Weekly_Tracker_Targets t
    JOIN dbo.PROPERTY_0 p ON p.PROPERTY_NAME LIKE '%' + SUBSTRING(t.Levels, CHARINDEX(' ', t.Levels)+1, 100) + '%'
    WHERE t.Academic_Yr = '26-27 AY'
    GROUP BY t.Levels, p.PROPERTY_KEY, p.PROPERTY_NAME
""")
for r in cur.fetchall():
    print(f"  Levels='{r[0]}' -> KEY={r[1]}, NAME={r[2]}")

# Also check Adaptive_Weekly_Tracker_Targets_2025 for PY1
print("\n=== Adaptive_Weekly_Tracker_Targets_2025 columns ===")
cur = conn.execute("SELECT TOP 0 * FROM dbo.Adaptive_Weekly_Tracker_Targets_2025")
print("  ", [d[0] for d in cur.description])
cur2 = conn.execute("SELECT DISTINCT Academic_Yr FROM dbo.Adaptive_Weekly_Tracker_Targets_2025")
for r in cur2.fetchall():
    print(f"  AY: {r[0]}")
cur3 = conn.execute("""
    SELECT TOP 3 Levels, Academic_Yr, Week_Beginning, Total_Weekly, New_Weekly, Renewal_Weekly
    FROM dbo.Adaptive_Weekly_Tracker_Targets_2025
    WHERE Levels LIKE '%48%West%'
""")
for r in cur3.fetchall():
    print(f"  {r[0]} | AY={r[1]} | Wk={r[2]} | Total={r[3]} | New={r[4]} | Ren={r[5]}")

conn.close()
