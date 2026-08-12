import sys, os
sys.path.insert(0, r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts')
from helpers import load_env, SafeConnection
env = load_env()

conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# 1. EMP_ENTRATA_TITLE_GROUP_MAPPING - the Entrata Title Groups Mgmt table
print('=== EMP_ENTRATA_TITLE_GROUP_MAPPING ===')
cols = conn.fetchall("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'EMP_ENTRATA_TITLE_GROUP_MAPPING' ORDER BY ORDINAL_POSITION")
for c in cols: print(f'  {c[0]}')
cnt = conn.fetchall("SELECT COUNT(*) FROM dbo.EMP_ENTRATA_TITLE_GROUP_MAPPING")
print(f'  Rows: {cnt[0][0]}')
sample = conn.fetchall("SELECT TOP 5 * FROM dbo.EMP_ENTRATA_TITLE_GROUP_MAPPING")
for s in sample: print(f'  {s}')

# 2. EMP_TITLE_GROUP_MGMT
print('\n=== EMP_TITLE_GROUP_MGMT ===')
cols = conn.fetchall("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'EMP_TITLE_GROUP_MGMT' ORDER BY ORDINAL_POSITION")
for c in cols: print(f'  {c[0]}')
cnt = conn.fetchall("SELECT COUNT(*) FROM dbo.EMP_TITLE_GROUP_MGMT")
print(f'  Rows: {cnt[0][0]}')
sample = conn.fetchall("SELECT TOP 5 * FROM dbo.EMP_TITLE_GROUP_MGMT")
for s in sample: print(f'  {s}')

# 3. EMP_TITLE_GROUPS
print('\n=== EMP_TITLE_GROUPS ===')
cols = conn.fetchall("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'EMP_TITLE_GROUPS' ORDER BY ORDINAL_POSITION")
for c in cols: print(f'  {c[0]}')
cnt = conn.fetchall("SELECT COUNT(*) FROM dbo.EMP_TITLE_GROUPS")
print(f'  Rows: {cnt[0][0]}')
sample = conn.fetchall("SELECT TOP 5 * FROM dbo.EMP_TITLE_GROUPS ORDER BY TITLE_GROUP")
for s in sample: print(f'  {s}')

# 4. EMPLOYEE_SECURITY tables
print('\n=== EMPLOYEE_SECURITY ===')
cols = conn.fetchall("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'EMPLOYEE_SECURITY' ORDER BY ORDINAL_POSITION")
for c in cols: print(f'  {c[0]}')
cnt = conn.fetchall("SELECT COUNT(*) FROM dbo.EMPLOYEE_SECURITY")
print(f'  Rows: {cnt[0][0]}')

print('\n=== EMPLOYEE_SECURITY_0 ===')
cols = conn.fetchall("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'EMPLOYEE_SECURITY_0' ORDER BY ORDINAL_POSITION")
for c in cols: print(f'  {c[0]}')
cnt = conn.fetchall("SELECT COUNT(*) FROM dbo.EMPLOYEE_SECURITY_0")
print(f'  Rows: {cnt[0][0]}')

# 5. EMPLOYEE_SOFT_TERMINATION_OVERRIDES
print('\n=== EMPLOYEE_SOFT_TERMINATION_OVERRIDES ===')
cols = conn.fetchall("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'EMPLOYEE_SOFT_TERMINATION_OVERRIDES' ORDER BY ORDINAL_POSITION")
for c in cols: print(f'  {c[0]}')
cnt = conn.fetchall("SELECT COUNT(*) FROM dbo.EMPLOYEE_SOFT_TERMINATION_OVERRIDES")
print(f'  Rows: {cnt[0][0]}')

conn.close()
