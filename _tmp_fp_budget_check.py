import sys
sys.path.insert(0, '../Help Ticket Triage/bi-triage-agent/scripts')
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, 'DB_APP_SUPPORT', None, direct=True)

# EMERALD PREMIUM = FLOORPLAN_KEY 189261, PROPERTY_KEY 1069, AY 2026
for lt in ('RENEWAL', 'NEW'):
    cur = conn.execute("""
        SELECT ISNULL(SUM(BEDS),0), ISNULL(SUM(RATE_EXTENDED1),0)
        FROM dbo.FORECAST_BUDGET_TIERS
        WHERE PROPERTY_KEY = 1069 AND FLOORPLAN_KEY = 189261 AND AY = 2026
          AND LEASE_TYPE = ? AND TIER_NUMBER <> 0
    """, (lt,))
    beds, rate_ext = cur.fetchone()
    print(f"{lt}: BEDS={beds}, RATE_EXT={rate_ext}, AVG={rate_ext/beds if beds else 0:.4f}")

# Combined
cur = conn.execute("""
    SELECT ISNULL(SUM(BEDS),0), ISNULL(SUM(RATE_EXTENDED1),0)
    FROM dbo.FORECAST_BUDGET_TIERS
    WHERE PROPERTY_KEY = 1069 AND FLOORPLAN_KEY = 189261 AND AY = 2026
      AND TIER_NUMBER <> 0
""")
beds, rate_ext = cur.fetchone()
print(f"TOTAL: BEDS={beds}, RATE_EXT={rate_ext}, AVG={rate_ext/beds if beds else 0:.4f}")
print(f"Truth shows $1,877.50 — DB shows {rate_ext/beds if beds else 0:.2f}")

conn.close()
