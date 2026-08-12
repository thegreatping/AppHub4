"""Explore DB tables for weekly leasing velocity data (leases per week)."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# All tables
print("=== All tables in DB_APP_SUPPORT ===")
cur = conn.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME")
for r in cur.fetchall():
    print(f"  {r[0]}")

print("\n=== FLOORPLAN_ACTUALS_RENT columns ===")
cur = conn.execute("SELECT TOP 0 * FROM dbo.FLOORPLAN_ACTUALS_RENT")
cols = [d[0] for d in cur.description]
print("  ", cols)

print("\n=== Sample FLOORPLAN_ACTUALS_RENT for 48 WEST (9797) AY=2026 ===")
cur = conn.execute("""
    SELECT TOP 20 ROW_NUMBER, AY, FLOORPLAN_KEY, FLOORPLAN,
           LEASED_COUNT_NEW, LEASED_COUNT_RENEWAL, LEASED_COUNT_TOTAL,
           INTERVAL_TYPE_CONFORMED
    FROM dbo.FLOORPLAN_ACTUALS_RENT
    WHERE PROPERTY_KEY=9797 AND AY=2026
    ORDER BY FLOORPLAN_KEY, ROW_NUMBER
""")
cols = [d[0] for d in cur.description]
for r in cur.fetchall():
    print("  ", dict(zip(cols, r)))

# Check if there's a property-level actuals table (not floorplan-level)
print("\n=== Tables with ACTUALS or WEEKLY ===")
cur = conn.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE '%ACTUAL%' OR TABLE_NAME LIKE '%WEEK%' ORDER BY TABLE_NAME")
for r in cur.fetchall():
    print(f"  {r[0]}")

conn.close()
