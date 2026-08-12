import sys
sys.path.insert(0, '../Help Ticket Triage/bi-triage-agent/scripts')
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, 'DB_APP_SUPPORT', None, direct=True)

# Show all individual tiers for EMERALD PREMIUM
cur = conn.execute("""
    SELECT LEASE_TYPE, TIER_NUMBER, BEDS, RATE, RATE_EXTENDED1
    FROM dbo.FORECAST_BUDGET_TIERS
    WHERE PROPERTY_KEY = 1069 AND FLOORPLAN_KEY = 189261 AND AY = 2026 AND TIER_NUMBER <> 0
    ORDER BY LEASE_TYPE, TIER_NUMBER
""")
print("Individual tiers:")
for r in cur.fetchall():
    print(r)

print()
# What if Truth rounds avg_rate to nearest dollar, uses that for total?
r_beds, r_ext = 2, 3659.71
n_beds, n_ext = 2, 3850.00
r_avg = r_ext / r_beds    # 1829.855
n_avg = n_ext / n_beds    # 1925.00

print(f"R avg raw: {r_avg:.4f}")
print(f"N avg raw: {n_avg:.4f}")

# Method 1: straight weighted
print(f"\nMethod 1 (raw): {(r_ext+n_ext)/(r_beds+n_beds):.2f}")

# Method 2: round each avg to nearest dollar, then weighted total
r_rounded = round(r_avg)
n_rounded = round(n_avg)
total_m2 = (r_rounded * r_beds + n_rounded * n_beds) / (r_beds + n_beds)
print(f"Method 2 (round each avg first): R={r_rounded}, N={n_rounded} -> Total={total_m2:.2f}")

# Method 3: average of rounded avgs (simple avg, not weighted)
print(f"Method 3 (simple avg of rounded): {(r_rounded+n_rounded)/2:.2f}")

conn.close()
