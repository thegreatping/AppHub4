"""Check CULTIVATE_NOMINATION standing values and xtemp.EMPLOYEE_F structure."""
import sys, os
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

print("=" * 60)
print("1. DISTINCT ASSOCIATE_STANDING_CHOICE values")
print("=" * 60)
cur = conn.execute("SELECT DISTINCT ASSOCIATE_STANDING_CHOICE FROM dbo.CULTIVATE_NOMINATION ORDER BY ASSOCIATE_STANDING_CHOICE")
for r in cur.fetchall():
    print(f"  '{r[0]}'")

print("\n" + "=" * 60)
print("2. Sample nominations (top 5)")
print("=" * 60)
cur = conn.execute("SELECT TOP 5 ID, ASSOCIATE_NOMINATED, ASSOCIATE_STANDING_CHOICE, ASSOCIATE_STANDING_TEXT, NOMINATED_BY FROM dbo.CULTIVATE_NOMINATION ORDER BY ID DESC")
for r in cur.fetchall():
    print(f"  ID={r[0]} | Name={r[1]} | Choice={r[2]} | Text={r[3]} | By={r[4]}")

print("\n" + "=" * 60)
print("3. Total nomination count")
print("=" * 60)
cur = conn.execute("SELECT COUNT(*) FROM dbo.CULTIVATE_NOMINATION")
print(f"  {cur.fetchone()[0]} rows")

print("\n" + "=" * 60)
print("4. xtemp.EMPLOYEE_F - check if exists")
print("=" * 60)
try:
    cur = conn.execute("""SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH 
                  FROM INFORMATION_SCHEMA.COLUMNS 
                  WHERE TABLE_NAME = 'EMPLOYEE_F' AND TABLE_SCHEMA = 'xtemp'
                  ORDER BY ORDINAL_POSITION""")
    cols = cur.fetchall()
    if cols:
        for c in cols:
            print(f"  {c[0]} ({c[1]}, {c[2]})")
    else:
        print("  TABLE NOT FOUND in xtemp schema")
        cur = conn.execute("""SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
                      WHERE TABLE_NAME LIKE '%EMPLOYEE%' ORDER BY TABLE_SCHEMA, TABLE_NAME""")
        for r in cur.fetchall():
            print(f"    {r[0]}.{r[1]}")
except Exception as e:
    print(f"  Error: {e}")

print("\n" + "=" * 60)
print("5. APP_ADMINS for APP_ID=22")
print("=" * 60)
cur = conn.execute("SELECT * FROM dbo.APP_ADMINS WHERE APP_ID = 22")
cols = [d[0] for d in cur.description]
print(f"  Columns: {cols}")
for r in cur.fetchall():
    print(f"  {dict(zip(cols, r))}")
