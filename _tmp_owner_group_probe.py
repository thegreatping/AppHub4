import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files")
from helpers import SafeConnection, load_env

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
try:
    print('TABLES:')
    rows = conn.fetchall("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE '%OWNER%' OR TABLE_NAME LIKE '%PROPERTY_GROUP%' OR TABLE_NAME LIKE '%MARKET%' ORDER BY TABLE_NAME")
    for r in rows:
        print(r[0])

    print('\nOWNER_GROUP_0 columns:')
    rows = conn.fetchall("SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'OWNER_GROUP_0' ORDER BY ORDINAL_POSITION")
    for r in rows:
        print(r)

    print('\nPROPERTY_0 Owner-related columns:')
    rows = conn.fetchall("SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'PROPERTY_0' AND (COLUMN_NAME LIKE '%OWNER%' OR COLUMN_NAME LIKE '%GROUP%') ORDER BY ORDINAL_POSITION")
    for r in rows:
        print(r)

    print('\nSAMPLE OWNER_GROUP_0 rows:')
    cur = conn.execute("SELECT TOP 20 * FROM dbo.OWNER_GROUP_0 ORDER BY OWNER_GROUP")
    cols = [d[0] for d in cur.description]
    for row in cur.fetchall():
        print(dict(zip(cols, row)))
finally:
    conn.close()
