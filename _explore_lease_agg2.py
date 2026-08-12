"""Explore LEASE_AGG weekly complete leases for the chart."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "WH_PROD2", None)

PROP = 1069   # GeoCentral
FP   = 189260 # EMERALD
AY   = 2026

# Check DATE_KEY_AY structure — is it a week number?
print("=== DATE_KEY_AY range for AY2026 GeoCentral ===")
cur = conn.execute("""
    SELECT MIN(DATE_KEY_AY), MAX(DATE_KEY_AY), MIN(DATE_KEY), MAX(DATE_KEY), COUNT(DISTINCT DATE_KEY_AY)
    FROM WH_PROD2.dbo.LEASE_AGG
    WHERE PROPERTY_KEY=? AND AY=?
""", (PROP, AY))
print(cur.fetchone())

# Sample rows — key columns
print("\n=== Sample rows, key columns ===")
cur = conn.execute("""
    SELECT TOP 10
        DATE_KEY_AY, DATE_KEY, AY, FLOORPLAN_KEY,
        FLAG_FALL_TOTAL, FLAG_FALL_NEW, FLAG_FALL_RENEWAL,
        FLAG_THIS_WEEK_COMPLETES,
        FLAG_LEASE_VELOCITY_TOTAL, FLAG_LEASE_VELOCITY_NEW, FLAG_LEASE_VELOCITY_RENEWAL
    FROM WH_PROD2.dbo.LEASE_AGG
    WHERE PROPERTY_KEY=? AND AY=?
    ORDER BY DATE_KEY DESC
""", (PROP, AY))
cols = [d[0] for d in cur.description]
print(cols)
for r in cur.fetchall():
    print(dict(zip(cols, r)))

# What does the weekly aggregation look like? Group by week for the floorplan
print("\n=== Weekly complete leases for EMERALD AY2026 (group by AY week) ===")
cur = conn.execute("""
    SELECT DATE_KEY_AY,
           SUM(FLAG_FALL_TOTAL) AS total_complete,
           SUM(FLAG_FALL_NEW)   AS new_complete,
           SUM(FLAG_FALL_RENEWAL) AS ren_complete,
           MIN(DATE_KEY) AS week_start_date,
           COUNT(*) AS rows
    FROM WH_PROD2.dbo.LEASE_AGG
    WHERE PROPERTY_KEY=? AND FLOORPLAN_KEY=? AND AY=?
    GROUP BY DATE_KEY_AY
    ORDER BY DATE_KEY_AY
""", (PROP, FP, AY))
cols = [d[0] for d in cur.description]
print(cols)
for r in cur.fetchall():
    print(dict(zip(cols, r)))

# Same for PY1 (AY=2025)
print("\n=== Weekly complete leases for EMERALD AY2025 ===")
cur = conn.execute("""
    SELECT DATE_KEY_AY,
           SUM(FLAG_FALL_TOTAL) AS total_complete,
           SUM(FLAG_FALL_NEW)   AS new_complete,
           SUM(FLAG_FALL_RENEWAL) AS ren_complete,
           MIN(DATE_KEY) AS week_start_date
    FROM WH_PROD2.dbo.LEASE_AGG
    WHERE PROPERTY_KEY=? AND FLOORPLAN_KEY=? AND AY=?
    GROUP BY DATE_KEY_AY
    ORDER BY DATE_KEY_AY
""", (PROP, FP, 2025))
cols = [d[0] for d in cur.description]
for r in cur.fetchall():
    print(dict(zip(cols, r)))

conn.close()
