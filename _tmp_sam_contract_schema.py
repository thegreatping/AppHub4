"""Get full schema of VENDOR_CONTRACT and related tables."""
import sys
sys.path.insert(0, ".")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

print("=== VENDOR_CONTRACT columns ===")
rows = conn.fetchall("""
    SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE, COLUMN_DEFAULT
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'VENDOR_CONTRACT'
    ORDER BY ORDINAL_POSITION
""")
for r in rows:
    print(f"  {r[0]:40s} {r[1]:20s} len={r[2]}  null={r[3]}  default={r[4]}")

print("\n=== Row count ===")
r = conn.fetchone("SELECT COUNT(*) FROM dbo.VENDOR_CONTRACT")
print(f"  {r[0]} rows")

print("\n=== Sample rows ===")
rows = conn.fetchall("SELECT TOP 3 * FROM dbo.VENDOR_CONTRACT ORDER BY 1 DESC")
if rows:
    # Print column values
    cols = conn.fetchall("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME='VENDOR_CONTRACT' ORDER BY ORDINAL_POSITION
    """)
    colnames = [c[0] for c in cols]
    for row in rows:
        for i, v in enumerate(row):
            print(f"  {colnames[i]}: {v}")
        print()
