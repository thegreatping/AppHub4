"""Check Adaptive tables for GeoCentral/48 WEST weekly leasing data."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Check Adaptive_Weekly_Tracker_Targets - what does '26-27 AY' mean? And week format?
print("=== Adaptive_Weekly_Tracker_Targets - distinct AY values ===")
cur = conn.execute("SELECT DISTINCT Academic_Yr FROM dbo.Adaptive_Weekly_Tracker_Targets ORDER BY Academic_Yr")
for r in cur.fetchall():
    print(f"  {r[0]}")

print("\n=== Adaptive_Weekly_Tracker_Targets - GeoCentral rows ===")
cur = conn.execute("""
    SELECT TOP 20 Levels, Academic_Yr, Week_Beginning, Total_Weekly, Renewal_Weekly, New_Weekly
    FROM dbo.Adaptive_Weekly_Tracker_Targets
    WHERE Levels LIKE '%GEOCENTRAL%' OR Levels LIKE '%GeoCentral%' OR Levels LIKE '%Geocentral%'
    ORDER BY Academic_Yr, Week_Beginning
""")
for r in cur.fetchall():
    print(f"  {r[0]} | AY={r[1]} | Wk={r[2]} | Total={r[3]} | Ren={r[4]} | New={r[5]}")

print("\n=== Adaptive_Weekly_Tracker_Targets - 48 WEST rows ===")
cur = conn.execute("""
    SELECT TOP 20 Levels, Academic_Yr, Week_Beginning, Total_Weekly, Renewal_Weekly, New_Weekly
    FROM dbo.Adaptive_Weekly_Tracker_Targets
    WHERE Levels LIKE '%48%WEST%' OR Levels LIKE '%48West%'
    ORDER BY Academic_Yr, Week_Beginning
""")
for r in cur.fetchall():
    print(f"  {r[0]} | AY={r[1]} | Wk={r[2]} | Total={r[3]} | Ren={r[4]} | New={r[5]}")

# Check Adaptive_Z_WeeklyTracker for actuals - what account codes have leasing?
print("\n=== Adaptive_Z_WeeklyTracker - distinct Account_Name values ===")
cur = conn.execute("SELECT DISTINCT Account_Name FROM dbo.Adaptive_Z_WeeklyTracker ORDER BY Account_Name")
for r in cur.fetchall():
    print(f"  {r[0]}")

print("\n=== Adaptive_Z_WeeklyTracker - GeoCentral actual new leases ===")
cur = conn.execute("""
    SELECT TOP 20 Level_Name, Academic_Yr, Week_Beginning, Account_Name, Data_Value
    FROM dbo.Adaptive_Z_WeeklyTracker
    WHERE (Level_Name LIKE '%GEOCENTRAL%' OR Level_Name LIKE '%GeoCentral%')
      AND Account_Name LIKE '%New%'
    ORDER BY Academic_Yr DESC, Week_Beginning
""")
for r in cur.fetchall():
    print(f"  {r[0]} | AY={r[1]} | Wk={r[2]} | Acct={r[3]} | Val={r[4]}")

conn.close()
