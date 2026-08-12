"""Explore LEASE_AGG and LEASE_AGG_F for weekly complete leases by floorplan."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()

# WH_PROD2 connection (Fabric warehouse, NOT SQL DB)
conn = SafeConnection(env, "WH_PROD2", None)

# GeoCentral = 1069, EMERALD floorplan = 189260
PROP = 1069
FP   = 189260
AY   = 2026

print("=== LEASE_AGG_F columns ===")
try:
    cur = conn.execute("SELECT TOP 0 * FROM WH_PROD2.dbo.LEASE_AGG_F")
    cols = [d[0] for d in cur.description]
    print(cols)
except Exception as e:
    print("LEASE_AGG_F error:", e)

print("\n=== LEASE_AGG columns ===")
try:
    cur = conn.execute("SELECT TOP 0 * FROM WH_PROD2.dbo.LEASE_AGG")
    cols = [d[0] for d in cur.description]
    print(cols)
except Exception as e:
    print("LEASE_AGG error:", e)

print("\n=== LEASE_AGG_F sample for GeoCentral/EMERALD AY2026 ===")
try:
    cur = conn.execute("""
        SELECT TOP 5 *
        FROM WH_PROD2.dbo.LEASE_AGG_F
        WHERE PROPERTY_KEY=? AND FLOORPLAN_KEY=? AND AY=?
        ORDER BY DATE_KEY DESC
    """, (PROP, FP, AY))
    cols = [d[0] for d in cur.description]
    print(cols)
    for r in cur.fetchall():
        print(dict(zip(cols, r)))
except Exception as e:
    print("Error:", e)

print("\n=== Look for weekly complete leases columns in LEASE_AGG ===")
try:
    cur = conn.execute("""
        SELECT TOP 5 *
        FROM WH_PROD2.dbo.LEASE_AGG
        WHERE PROPERTY_KEY=? AND FLOORPLAN_KEY=? AND AY=?
        ORDER BY DATE_KEY DESC
    """, (PROP, FP, AY))
    cols = [d[0] for d in cur.description]
    print(cols)
    for r in cur.fetchall():
        print(dict(zip(cols, r)))
except Exception as e:
    print("LEASE_AGG FP-level error:", e)

# Try property-level
print("\n=== LEASE_AGG property-level, AY week columns ===")
try:
    cur = conn.execute("""
        SELECT TOP 3 *
        FROM WH_PROD2.dbo.LEASE_AGG
        WHERE PROPERTY_KEY=? AND AY=?
        ORDER BY DATE_KEY DESC
    """, (PROP, AY))
    cols = [d[0] for d in cur.description]
    print(cols)
    for r in cur.fetchall():
        row = dict(zip(cols, r))
        # Show only non-null columns
        print({k: v for k, v in row.items() if v is not None and v != 0})
except Exception as e:
    print("Error:", e)

conn.close()
