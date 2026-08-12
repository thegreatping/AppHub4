"""Check EMPLOYEE_SECURITY_0 structure for PDM dropdowns."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import SafeConnection, load_env

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Check columns
cur = conn.execute("""
    SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'EMPLOYEE_SECURITY_0' ORDER BY ORDINAL_POSITION
""")
print("=== EMPLOYEE_SECURITY_0 columns ===")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

cur = conn.execute("SELECT COUNT(*) FROM dbo.EMPLOYEE_SECURITY_0 WHERE FLAG_ACTIVE = 1")
print(f"\nActive employees: {cur.fetchone()[0]}")

# Sample row
cur = conn.execute("SELECT TOP 3 EMPLOYEE_CODE, NAME_FULL, EMAIL, TITLE, FLAG_ACTIVE FROM dbo.EMPLOYEE_SECURITY_0 WHERE FLAG_ACTIVE = 1 ORDER BY NAME_FULL")
print("\nSample rows:")
for r in cur.fetchall():
    print(f"  {r[0]} | {r[1]} | {r[2]} | {r[3]}")

conn.close()
