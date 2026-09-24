"""Get sample data and distinct values for VENDOR_CONTRACT."""
import sys
sys.path.insert(0, ".")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

r = conn.fetchall("SELECT COUNT(*) FROM dbo.VENDOR_CONTRACT")[0]
print(f"Row count: {r[0]}")

print("\n=== Distinct CONTRACT_LEVEL ===")
for r in conn.fetchall("SELECT DISTINCT CONTRACT_LEVEL FROM dbo.VENDOR_CONTRACT ORDER BY 1"):
    print(f"  {r[0]}")

print("\n=== Distinct CONTRACT_BILLING_FREQUENCY ===")
for r in conn.fetchall("SELECT DISTINCT CONTRACT_BILLING_FREQUENCY FROM dbo.VENDOR_CONTRACT ORDER BY 1"):
    print(f"  {r[0]}")

print("\n=== Distinct FLAG_ACTIVE ===")
for r in conn.fetchall("SELECT DISTINCT FLAG_ACTIVE FROM dbo.VENDOR_CONTRACT ORDER BY 1"):
    print(f"  {r[0]}")

print("\n=== Sample rows (most recent) ===")
rows = conn.fetchall("""
    SELECT TOP 5
        CONTRACT_KEY, CONTRACT_NAME, VENDOR_NAME, PROPERTY_NAME,
        CONTRACT_LEVEL, CONTRACT_AMOUNT, CONTRACT_BILLING_FREQUENCY,
        DATETIME_BEGIN, DATETIME_END, FLAG_ACTIVE, FLAG_ALERT_STATUS
    FROM dbo.VENDOR_CONTRACT
    ORDER BY CONTRACT_KEY DESC
""")
for r in rows:
    print(f"  KEY={r[0]} | {r[1]} | vendor={r[2]} | prop={r[3]}")
    print(f"    level={r[4]} | amt={r[5]} | freq={r[6]} | begin={r[7]} | end={r[8]} | active={r[9]} | alert={r[10]}")
