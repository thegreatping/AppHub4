"""Research PDM table structures in DB_APP_SUPPORT."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import SafeConnection, load_env

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# 1. PROPERTY_0 columns
print("=== PROPERTY_0 columns ===")
cur = conn.execute("""
    SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'PROPERTY_0'
    ORDER BY ORDINAL_POSITION
""")
for r in cur.fetchall():
    print(f"  {r[0]:40s} {r[1]:15s} {str(r[2] or ''):>6s}  {r[3]}")

# 2. Row count
cur = conn.execute("SELECT COUNT(*) FROM dbo.PROPERTY_0")
print(f"\nPROPERTY_0 row count: {cur.fetchone()[0]}")

# 3. Status combos
cur = conn.execute("""
    SELECT FLAG_ACTIVE, FLAG_REPORTABLE, FLAG_DISPOSITIONED, FLAG_MANAGED, COUNT(*) cnt
    FROM dbo.PROPERTY_0
    GROUP BY FLAG_ACTIVE, FLAG_REPORTABLE, FLAG_DISPOSITIONED, FLAG_MANAGED
    ORDER BY cnt DESC
""")
print("\n=== Status combinations ===")
for r in cur.fetchall():
    print(f"  Active={r[0]} Report={r[1]} Disp={r[2]} Managed={r[3]}  count={r[4]}")

# 4. Related tables
print("\n=== Related tables ===")
for tbl in ['PROPERTY_GROUP_0', 'PARENT_PROPERTY', 'COMP_PROPERTY', 'COMP_ASSIGNMENTS', 'MARKETS', 'OWNER_GROUP_0', 'PAYROLL_ENTITY_0']:
    cur = conn.execute(f"SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = '{tbl}'")
    exists = cur.fetchone()[0]
    if exists:
        cur = conn.execute(f"SELECT COUNT(*) FROM dbo.[{tbl}]")
        cnt = cur.fetchone()[0]
        print(f"  {tbl}: {cnt} rows")
    else:
        print(f"  {tbl}: NOT FOUND")

# 5. Sample active property (key fields only)
print("\n=== Sample PROPERTY_0 row (first active, non-null fields) ===")
cur = conn.execute("SELECT TOP 1 * FROM dbo.PROPERTY_0 WHERE FLAG_ACTIVE = 1 ORDER BY PROPERTY_NAME")
cols = [d[0] for d in cur.description]
row = cur.fetchone()
for c, v in zip(cols, row):
    if v is not None and str(v).strip():
        print(f"  {c}: {v}")

# 6. PROPERTY_GROUP_0 columns
print("\n=== PROPERTY_GROUP_0 columns ===")
cur = conn.execute("""
    SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'PROPERTY_GROUP_0' ORDER BY ORDINAL_POSITION
""")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

conn.close()
