"""Check 48 WEST weekly data and understand budget pace for leasing trend chart."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# 48 WEST weekly data CY=2026
print("=== L0_STATIC_HISTORY_BY_WEEK - 48 WEST (9797) FOR_AY=2026 ===")
cur = conn.execute("""
    SELECT PROPERTY_KEY, FOR_AY, LEASING_WEEK_NBR, LEASING_WEEK_REVERSE_ID,
           WEEK_START_DATE_MONDAY, WEEK_END_DATE_SUNDAY,
           HIST_WEEKLY_NEW, HIST_WEEKLY_RENEWAL,
           HIST_CUM_NEW, HIST_CUM_RENEWAL
    FROM dbo.L0_STATIC_HISTORY_BY_WEEK
    WHERE PROPERTY_KEY=9797 AND FOR_AY=2026
    ORDER BY LEASING_WEEK_NBR
""")
cols = [d[0] for d in cur.description]
rows = cur.fetchall()
print(f"  {len(rows)} weeks found")
for r in rows:
    d = dict(zip(cols, r))
    print(f"  Wk{d['LEASING_WEEK_NBR']} ({d['WEEK_START_DATE_MONDAY']}-{d['WEEK_END_DATE_SUNDAY']}): New={d['HIST_WEEKLY_NEW']} Ren={d['HIST_WEEKLY_RENEWAL']}")

# PY1 = 2025
print("\n=== 48 WEST (9797) FOR_AY=2025 (last 10 weeks) ===")
cur = conn.execute("""
    SELECT LEASING_WEEK_NBR, WEEK_START_DATE_MONDAY, WEEK_END_DATE_SUNDAY,
           HIST_WEEKLY_NEW, HIST_WEEKLY_RENEWAL
    FROM dbo.L0_STATIC_HISTORY_BY_WEEK
    WHERE PROPERTY_KEY=9797 AND FOR_AY=2025
    ORDER BY LEASING_WEEK_NBR
""")
rows2 = cur.fetchall()
print(f"  {len(rows2)} weeks found")
for r in rows2[-15:]:
    print(f"  Wk{r[0]} ({r[1]}-{r[2]}): New={r[3]} Ren={r[4]}")

# Check ADAPTIVE_WEEKLY_TRACKER_TARGETS for budget weekly pace
print("\n=== Adaptive_Weekly_Tracker_Targets columns ===")
cur = conn.execute("SELECT TOP 0 * FROM dbo.Adaptive_Weekly_Tracker_Targets")
print("  ", [d[0] for d in cur.description])
cur2 = conn.execute("SELECT TOP 5 * FROM dbo.Adaptive_Weekly_Tracker_Targets WHERE PROPERTY_KEY=9797 ORDER BY 1")
cols2 = [d[0] for d in cur2.description]
for r in cur2.fetchall():
    print("  ", dict(zip(cols2, r)))

# Also check Adaptive_Weekly_Tracker_Assumptions
print("\n=== Adaptive_Weekly_Tracker_Assumptions columns ===")
cur = conn.execute("SELECT TOP 0 * FROM dbo.Adaptive_Weekly_Tracker_Assumptions")
print("  ", [d[0] for d in cur.description])
cur2 = conn.execute("SELECT TOP 3 * FROM dbo.Adaptive_Weekly_Tracker_Assumptions WHERE PROPERTY_KEY=9797")
cols3 = [d[0] for d in cur2.description]
for r in cur2.fetchall():
    print("  ", dict(zip(cols3, r)))

# Also check the FORECAST_BUDGET_TIERS for total beds budget (to compute weekly pace)
print("\n=== Budget total beds for 48 WEST AY=2026 (all floorplans) ===")
cur = conn.execute("""
    SELECT SUM(BEDS) as TOTAL_BUDGET_BEDS, SUM(BED_TOTAL) as TOTAL_BEDS
    FROM dbo.FORECAST_BUDGET_TIERS
    WHERE PROPERTY_KEY=9797 AND AY=2026 AND TIER_NUMBER>0
""")
r = cur.fetchone()
print(f"  Total budgeted beds={r[0]}, Total FP beds={r[1]}")

conn.close()
