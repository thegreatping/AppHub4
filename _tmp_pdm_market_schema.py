from dotenv import load_dotenv
load_dotenv()
from helpers import load_env, SafeConnection

conn = SafeConnection(load_env(), 'DB_APP_SUPPORT', None, direct=True)
try:
    cols = conn.fetchall("""
        SELECT COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='PROPERTY_0'
          AND COLUMN_NAME IN ('FLAG_ACTIVE','FLAG_MANAGED','FLAG_DISPOSITIONED','STATUS','MARKET_CITY','MARKET_STATE','MARKET_CITY_STATE','PROPERTY_NAME','PROPERTY_KEY')
        ORDER BY ORDINAL_POSITION
    """)
    print('COLUMNS')
    for row in cols:
        print(row)
    print('\nCOUNTS')
    for sql in [
        "SELECT COUNT(*) FROM dbo.PROPERTY_0 WHERE FLAG_ACTIVE = 1",
        "SELECT COUNT(*) FROM dbo.PROPERTY_0 WHERE FLAG_MANAGED = 1 AND (FLAG_DISPOSITIONED = 0 OR FLAG_DISPOSITIONED IS NULL)",
        "SELECT COUNT(*) FROM dbo.PROPERTY_0 WHERE UPPER(STATUS) = 'ACTIVE'",
    ]:
        try:
            print(sql, conn.fetchall(sql)[0][0])
        except Exception as exc:
            print(sql, 'ERROR', exc)
finally:
    conn.close()
