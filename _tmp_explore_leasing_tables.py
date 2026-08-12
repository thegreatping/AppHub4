"""Explore weekly leasing data tables for the new Leasing Trend chart."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Check FLOORPLAN_ACTUALS_RENT columns
print("=== FLOORPLAN_ACTUALS_RENT columns ===")
cur = conn.execute("SELECT TOP 0 * FROM dbo.FLOORPLAN_ACTUALS_RENT")
print([d[0] for d in cur.description])

# Sample data for GeoCentral 1X1A floorplan (need to find a floorplan key)
# First get a floorplan
print("\n=== Floorplans for GeoCentral (1069) ===")
cur = conn.execute("SELECT TOP 5 FLOORPLAN_KEY, FLOORPLAN, AY FROM dbo.FORECAST_BUDGET_TIERS WHERE PROPERTY_KEY=1069 AND AY=2026 GROUP BY FLOORPLAN_KEY, FLOORPLAN, AY ORDER BY FLOORPLAN")
for r in cur.fetchall():
    print(f"  KEY={r[0]}, FLOORPLAN={r[1]}, AY={r[2]}")

print("\n=== Sample FLOORPLAN_ACTUALS_RENT for GeoCentral AY=2026 ===")
cur = conn.execute("SELECT TOP 10 * FROM dbo.FLOORPLAN_ACTUALS_RENT WHERE PROPERTY_KEY=1069 AND AY=2026 ORDER BY ROW_NUMBER, FLOORPLAN_KEY")
cols = [d[0] for d in cur.description]
print("  Cols:", cols)
for r in cur.fetchall():
    print("  ", dict(zip(cols, r)))

# Check if there's a property-level weekly table
print("\n=== Tables with WEEK in the name ===")
cur = conn.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE '%WEEK%' OR TABLE_NAME LIKE '%WEEKLY%' ORDER BY TABLE_NAME")
for r in cur.fetchall():
    print(f"  {r[0]}")

print("\n=== Tables with LEASE in the name ===")
cur = conn.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE '%LEASE%' ORDER BY TABLE_NAME")
for r in cur.fetchall():
    print(f"  {r[0]}")

print("\n=== All FORECAST_ tables ===")
cur = conn.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE 'FORECAST_%' ORDER BY TABLE_NAME")
for r in cur.fetchall():
    print(f"  {r[0]}")

conn.close()
