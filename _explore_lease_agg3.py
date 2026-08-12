"""Confirm weekly completes using velocity flags and week numbering for recent weeks."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "WH_PROD2", None)

PROP = 1069   # GeoCentral
FP   = 189260 # EMERALD
AY   = 2026

# Screenshot shows W40=20260601, W41=20260608...W48=20260727
# W1 = June 1 - 39*7 = Sep 1, 2025
# AY week = DATEDIFF(week, '2025-08-31', date) + 1  -- using Sunday-based weeks
# Or simpler: DATEDIFF(day, '2025-09-01', date) / 7 + 1

# Get EMERALD data for recent weeks using both approaches
print("=== Weekly actuals for EMERALD AY2026 — recent window ===")
cur = conn.execute("""
    SELECT
        DATEDIFF(day, '2025-09-01',
            CONVERT(date, CAST(DATE_KEY AS varchar(8)))) / 7 + 1 AS ay_week,
        MAX(DATE_KEY) AS week_end_date,
        -- Velocity flags = "this week" metrics (not cumulative)
        MAX(FLAG_LEASE_VELOCITY_TOTAL)   AS vel_total,
        MAX(FLAG_LEASE_VELOCITY_NEW)     AS vel_new,
        MAX(FLAG_LEASE_VELOCITY_RENEWAL) AS vel_ren,
        -- Cumulative at end of week
        MAX(FLAG_FALL_TOTAL)   AS cum_total,
        MAX(FLAG_FALL_NEW)     AS cum_new,
        MAX(FLAG_FALL_RENEWAL) AS cum_ren
    FROM WH_PROD2.dbo.LEASE_AGG
    WHERE PROPERTY_KEY=? AND FLOORPLAN_KEY=? AND AY=?
    AND DATE_KEY >= 20260525  -- roughly W39 onward
    GROUP BY DATEDIFF(day, '2025-09-01', CONVERT(date, CAST(DATE_KEY AS varchar(8)))) / 7 + 1
    ORDER BY ay_week
""", (PROP, FP, AY))
cols = [d[0] for d in cur.description]
print(cols)
for r in cur.fetchall():
    print(dict(zip(cols, r)))

# Check PY1 (AY=2025) same weeks — W1 for 2025 = Sep 2, 2024 (first Monday in Sep)
print("\n=== PY1 (AY2025) weekly for EMERALD, W40-W52 ===")
cur = conn.execute("""
    SELECT
        DATEDIFF(day, '2024-09-02',
            CONVERT(date, CAST(DATE_KEY AS varchar(8)))) / 7 + 1 AS ay_week,
        MAX(DATE_KEY) AS week_end_date,
        MAX(FLAG_LEASE_VELOCITY_TOTAL)   AS vel_total,
        MAX(FLAG_FALL_TOTAL)             AS cum_total
    FROM WH_PROD2.dbo.LEASE_AGG
    WHERE PROPERTY_KEY=? AND FLOORPLAN_KEY=? AND AY=2025
    AND DATE_KEY >= 20250602  -- roughly W40 of AY2025
    GROUP BY DATEDIFF(day, '2024-09-02', CONVERT(date, CAST(DATE_KEY AS varchar(8)))) / 7 + 1
    ORDER BY ay_week
""", (PROP, FP))
cols = [d[0] for d in cur.description]
for r in cur.fetchall():
    print(dict(zip(cols, r)))

# Also check: what is FLAG_LEASE_VELOCITY_TOTAL at the property level for week 48?
# Screenshot shows GeoCentral W48 Complete This Week = 2
print("\n=== Property-level W48 (20260727) velocity check ===")
cur = conn.execute("""
    SELECT SUM(FLAG_LEASE_VELOCITY_TOTAL) AS prop_vel_total,
           SUM(FLAG_FALL_TOTAL) AS prop_cum_total,
           COUNT(DISTINCT FLOORPLAN_KEY) AS fp_count
    FROM WH_PROD2.dbo.LEASE_AGG
    WHERE PROPERTY_KEY=? AND AY=? AND DATE_KEY=20260728
""", (PROP, AY))
print(cur.fetchone())

conn.close()
