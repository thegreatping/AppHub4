from dotenv import load_dotenv
load_dotenv()
from helpers import load_env, SafeConnection

conn = SafeConnection(load_env(), 'DB_APP_SUPPORT', None, direct=True)
try:
    print('=== EMPLOYEE_F key/code columns in WH_STAGING skipped here ===')
    for table, col in [
        ('EMP_ENTRATA_GROUP_ASSIGNMENTS', 'ID'),
        ('EMP_ENTRATA_DEPARTMENT', 'ID'),
        ('EMP_ENTRATA_PERMISSION_GROUP', 'ID'),
        ('EMP_ENTRATA_PROPERTY_GROUP', 'ID'),
    ]:
        rows = conn.fetchall("""
            SELECT COLUMNPROPERTY(OBJECT_ID('dbo.' + ?), ?, 'IsIdentity') AS is_identity,
                   COLUMNPROPERTY(OBJECT_ID('dbo.' + ?), ?, 'AllowsNull') AS allows_null
        """, (table, col, table, col))
        print(table, col, rows[0])
finally:
    conn.close()

conn2 = SafeConnection(load_env(), 'WH_STAGING', None)
try:
    cols = conn2.fetchall("""
        SELECT COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='EMPLOYEE_F'
          AND COLUMN_NAME IN ('EMPLOYEE_KEY','EMPLOYEE_CODE','NAME_FIRST','NAME_LAST','STATUS')
        ORDER BY ORDINAL_POSITION
    """)
    print('\n=== WH_STAGING.dbo.EMPLOYEE_F relevant columns ===')
    for row in cols:
        print(row)
finally:
    conn2.close()
