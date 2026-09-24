from dotenv import load_dotenv
load_dotenv()
from helpers import load_env, SafeConnection

conn = SafeConnection(load_env(), 'DB_APP_SUPPORT', None, direct=True)
try:
    rows = conn.fetchall("""
        SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='EMPLOYEE_SOFT_TERMINATION_OVERRIDES'
        ORDER BY ORDINAL_POSITION
    """)
    for row in rows:
        print(row)
finally:
    conn.close()
