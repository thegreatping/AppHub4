import sys, os
sys.path.insert(0, r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts')
from helpers import load_env, SafeConnection
env = load_env()

conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# What does EDM manage? Check EMPLOYEE_0 for key fields an admin would edit
cols = conn.fetchall("""
    SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'EMPLOYEE_0'
    ORDER BY ORDINAL_POSITION
""")
print("=== All EMPLOYEE_0 columns ===")
for i, c in enumerate(cols):
    print(f"  {i+1:3}. {c[0]}")

# Sample row
print("\n=== Sample active employee ===")
row = conn.fetchall("SELECT TOP 1 * FROM dbo.EMPLOYEE_0 WHERE FLAG_ACTIVE = 1 AND EMAIL LIKE '%peakmade%'")
if row:
    for i, c in enumerate(cols):
        val = row[0][i]
        if val is not None and val != '' and val != 0:
            print(f"  {c[0]:35} = {val}")

conn.close()
