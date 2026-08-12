"""Check APP_LIST schema + current rows for RFS 2.0 setup."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

cur = conn.execute("""
    SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='APP_LIST'
    ORDER BY ORDINAL_POSITION
""")
print("APP_LIST columns:")
for r in cur.fetchall():
    print(f"  {r[0]} ({r[1]}) nullable={r[2]} maxlen={r[3]}")

cur = conn.execute("SELECT * FROM dbo.APP_LIST ORDER BY App_ID")
cols = [d[0] for d in cur.description]
print(f"\nRows (cols: {cols}):")
for r in cur.fetchall():
    print(f"  {dict(zip(cols, r))}")

conn.close()
