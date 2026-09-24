"""Get a broader sample and check vendors/properties."""
import sys
sys.path.insert(0, ".")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

print("=== Distinct vendors ===")
for r in conn.fetchall("SELECT DISTINCT VENDOR_NAME FROM dbo.VENDOR_CONTRACT ORDER BY 1"):
    print(f"  {r[0]}")

print("\n=== Rows with richer data ===")
rows = conn.fetchall("""
    SELECT TOP 10
        CONTRACT_KEY, CONTRACT_NAME, VENDOR_NAME, PROPERTY_NAME,
        CONTRACT_LEVEL, CONTRACT_AMOUNT, CONTRACT_BILLING_FREQUENCY,
        DATETIME_BEGIN, DATETIME_END, FLAG_ACTIVE, FLAG_ALERT_STATUS,
        CONTRACT_FOLDER, LISTING_URL
    FROM dbo.VENDOR_CONTRACT
    WHERE CONTRACT_AMOUNT IS NOT NULL
    ORDER BY CONTRACT_KEY DESC
""")
for r in rows:
    print(f"  KEY={r[0]} | {r[1]} | vendor={r[2]} | prop={r[3]}")
    print(f"    level={r[4]} | amt={r[5]} | freq={r[6]} | begin={r[7]} | end={r[8]}")
    print(f"    active={r[9]} | alert={r[10]} | folder={r[11]} | url={r[12]}")
    print()
