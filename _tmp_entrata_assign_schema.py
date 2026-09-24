from dotenv import load_dotenv
load_dotenv()
from helpers import load_env, SafeConnection

TABLES = [
    'EMP_ENTRATA_GROUP_ASSIGNMENTS',
    'EMP_ENTRATA_DEPARTMENT',
    'EMP_ENTRATA_PERMISSION_GROUP',
    'EMP_ENTRATA_PROPERTY_GROUP',
    'EMP_ENTRATA_TITLE_GROUP_MAPPING',
]

conn = SafeConnection(load_env(), 'DB_APP_SUPPORT', None, direct=True)
try:
    for table in TABLES:
        print(f'\n=== dbo.{table} ===')
        cols = conn.fetchall("""
            SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE, ORDINAL_POSITION
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME=?
            ORDER BY ORDINAL_POSITION
        """, (table,))
        if not cols:
            print('  NOT FOUND')
            continue
        for name, dtype, length, nullable, pos in cols:
            suffix = f'({length})' if length else ''
            print(f'  {pos:02d}. {name:<35s} {dtype}{suffix:<10s} nullable={nullable}')
        count = conn.fetchall(f'SELECT COUNT(*) FROM dbo.[{table}]')[0][0]
        print(f'  rows={count}')
        sample = conn.fetchall(f'SELECT TOP 5 * FROM dbo.[{table}]')
        for row in sample:
            print('  sample:', row)
finally:
    conn.close()
