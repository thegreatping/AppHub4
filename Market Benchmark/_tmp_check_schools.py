import sys, os
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import SafeConnection, load_env

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# How do schools link to parent properties? Check for any junction/assignment table
rows = conn.execute("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME LIKE '%SCHOOL%' OR TABLE_NAME LIKE '%MARKET%'
    ORDER BY TABLE_NAME
""")
print("=== SCHOOL/MARKET TABLES ===")
for r in rows:
    print(f"  {r[0]}")

# Check if PROPERTY or PARENT_PROPERTY has a school_key
rows = conn.execute("""
    SELECT TABLE_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
    WHERE COLUMN_NAME LIKE '%SCHOOL%' AND TABLE_NAME NOT LIKE '%BAK%'
    ORDER BY TABLE_NAME
""")
print("\n=== COLUMNS REFERENCING SCHOOL ===")
for r in rows:
    print(f"  {r[0]}.{r[1]}")

# Check MARKET tables
rows = conn.execute("""
    SELECT TABLE_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'MARKETS' OR TABLE_NAME = 'MARKET'
    ORDER BY TABLE_NAME, COLUMN_NAME
""")
print("\n=== MARKET TABLE COLUMNS ===")
for r in rows:
    print(f"  {r[0]}.{r[1]}")

# Sample SCHOOLS data
rows = conn.execute("SELECT TOP 5 SCHOOL_KEY, SCHOOL_NAME, MARKET_KEY, MARKET_CITY_STATE, FLAG_ACTIVE FROM SCHOOLS ORDER BY SCHOOL_KEY")
print("\n=== SAMPLE SCHOOLS ===")
for r in rows:
    print(f"  {r}")

# Sample SCHOOL_FACT
rows = conn.execute("SELECT TOP 5 * FROM SCHOOL_FACT ORDER BY SCHOOL_KEY, AY")
print("\n=== SAMPLE SCHOOL_FACT ===")
for r in rows:
    print(f"  {r}")

# Count
rows = conn.execute("SELECT COUNT(*) FROM SCHOOLS WHERE FLAG_ACTIVE = 1")
print(f"\nActive schools: {rows[0][0]}")

conn.close()
