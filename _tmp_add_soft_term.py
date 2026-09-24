import sys, os
sys.path.insert(0, os.getcwd())
from dotenv import load_dotenv; load_dotenv()
from helpers import load_env, SafeConnection

env = load_env()

# Verify in EMPLOYEE_F
conn_wh = SafeConnection(env, 'WH_STAGING', None)
emp = conn_wh.fetchall("SELECT TOP 1 NAME_FIRST, NAME_LAST FROM dbo.EMPLOYEE_F WHERE EMPLOYEE_CODE='A5NB' AND LOAD_TYPE <> 'PRE-HIRE'")
conn_wh.close()
if not emp:
    print('ERROR: A5NB not found in EMPLOYEE_F'); sys.exit(1)
name_first, name_last = emp[0]
print(f'Found: {name_first} {name_last}')

# Add to DB_APP_SUPPORT overrides table
conn = SafeConnection(env, 'DB_APP_SUPPORT', None, direct=True)
existing = conn.fetchall("SELECT 1 FROM dbo.EMPLOYEE_SOFT_TERMINATION_OVERRIDES WHERE EMPLOYEE_CODE='A5NB'")
if existing:
    print('Already exists in overrides table')
else:
    conn.execute("""
        INSERT INTO dbo.EMPLOYEE_SOFT_TERMINATION_OVERRIDES
            (EMPLOYEE_CODE, FLAG_SOFT_TERMINATION, NAME_FIRST, NAME_LAST, REASON)
        VALUES (?, 1, ?, ?, ?)
    """, ('A5NB', name_first, name_last, 'Soft termination - keep AD account active'))
    conn.commit()
    print(f'Inserted A5NB {name_first} {name_last}')

row = conn.fetchall("SELECT EMPLOYEE_CODE, NAME_FIRST, NAME_LAST, FLAG_SOFT_TERMINATION, REASON FROM dbo.EMPLOYEE_SOFT_TERMINATION_OVERRIDES WHERE EMPLOYEE_CODE='A5NB'")
print(f'Verified: {row}')
conn.close()
