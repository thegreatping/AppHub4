import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import SafeConnection, load_env
env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Check the master comp map tables
rows = conn.execute("""
    SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'MktSrv_CompMap' ORDER BY ORDINAL_POSITION
""").fetchall()
print("=== MktSrv_CompMap COLUMNS ===")
for r in rows:
    print(f"  {r[0]}  ({r[1]})")

rows = conn.execute("SELECT TOP 5 * FROM MktSrv_CompMap ORDER BY 1").fetchall()
print("\n=== SAMPLE MktSrv_CompMap ===")
for r in rows:
    print(f"  {r}")

# FORECAST_COMP_LIST
rows = conn.execute("""
    SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'FORECAST_COMP_LIST' ORDER BY ORDINAL_POSITION
""").fetchall()
print("\n=== FORECAST_COMP_LIST COLUMNS ===")
for r in rows:
    print(f"  {r[0]}  ({r[1]})")

rows = conn.execute("SELECT TOP 5 * FROM FORECAST_COMP_LIST").fetchall()
print("\n=== SAMPLE FORECAST_COMP_LIST ===")
for r in rows:
    print(f"  {r}")

# Check vw_MS_Parent_to_Comp_Lookup
rows = conn.execute("SELECT TOP 5 * FROM vw_MS_Parent_to_Comp_Lookup ORDER BY 1").fetchall()
print("\n=== SAMPLE vw_MS_Parent_to_Comp_Lookup ===")
for r in rows:
    print(f"  {r}")

# Check COMP_ASSIGNMENT_FACT
rows = conn.execute("""
    SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'COMP_ASSIGNMENT_FACT' ORDER BY ORDINAL_POSITION
""").fetchall()
print("\n=== COMP_ASSIGNMENT_FACT COLUMNS ===")
for r in rows:
    print(f"  {r[0]}  ({r[1]})")

rows = conn.execute("SELECT TOP 5 * FROM COMP_ASSIGNMENT_FACT ORDER BY 1").fetchall()
print("\n=== SAMPLE COMP_ASSIGNMENT_FACT ===")
for r in rows:
    print(f"  {r}")

conn.close()
