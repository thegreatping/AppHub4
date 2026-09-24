"""Inspect VENDOR and Property_Vendors tables."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import load_env, SafeConnection

env  = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

for tbl in ["dbo.VENDOR", "dbo.Property_Vendors"]:
    print(f"\n=== {tbl} — row count ===")
    cnt = conn.scalar(f"SELECT COUNT(*) FROM {tbl}")
    print(f"  {cnt} rows")

    print(f"\n=== {tbl} — columns ===")
    rows = conn.fetchall(f"""
        SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = '{tbl.split('.')[0].strip('dbo')}' OR TABLE_SCHEMA = 'dbo'
          AND TABLE_NAME = '{tbl.split('.')[1]}'
        ORDER BY ORDINAL_POSITION
    """)
    # simpler approach
    cur = conn.execute(f"SELECT TOP 0 * FROM {tbl}")
    cols = [d[0] for d in cur.description]
    print("  " + ", ".join(cols))

    print(f"\n=== {tbl} — sample (3 rows) ===")
    cur = conn.execute(f"SELECT TOP 3 * FROM {tbl}")
    for row in cur.fetchall():
        d = dict(zip(cols, row))
        # truncate long values
        for k in list(d.keys()):
            if isinstance(d[k], (bytes, bytearray)):
                d[k] = f"<bytes len={len(d[k])}>"
            elif isinstance(d[k], str) and len(d[k]) > 80:
                d[k] = d[k][:80] + "..."
        for k, v in d.items():
            print(f"    {k}: {v}")
        print()
