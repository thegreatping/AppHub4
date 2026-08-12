"""Check CULTIVATE_NOMINATION standing values and xtemp.EMPLOYEE_F structure."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'de_remediation', 'scripts'))
from helpers import load_env, get_fabric_connection

env = load_env()

print("=" * 60)
print("1. DISTINCT ASSOCIATE_STANDING_CHOICE values")
print("=" * 60)
conn = get_fabric_connection(env, "DB_APP_SUPPORT")
cur = conn.cursor()
    cur.execute("SELECT DISTINCT ASSOCIATE_STANDING_CHOICE FROM dbo.CULTIVATE_NOMINATION ORDER BY ASSOCIATE_STANDING_CHOICE")
    rows = cur.fetchall()
    for r in rows:
        print(f"  '{r[0]}'")

    print()
    print("=" * 60)
    print("2. Sample nominations (top 5)")
    print("=" * 60)
    cur.execute("SELECT TOP 5 ID, ASSOCIATE_NOMINATED, ASSOCIATE_STANDING_CHOICE, ASSOCIATE_STANDING_TEXT, NOMINATED_BY FROM dbo.CULTIVATE_NOMINATION ORDER BY ID DESC")
    rows = cur.fetchall()
    for r in rows:
        print(f"  ID={r[0]} | Name={r[1]} | Choice={r[2]} | Text={r[3]} | By={r[4]}")

    print()
    print("=" * 60)
    print("3. Total nomination count")
    print("=" * 60)
    cur.execute("SELECT COUNT(*) FROM dbo.CULTIVATE_NOMINATION")
    print(f"  {cur.fetchone()[0]} rows")

    print()
    print("=" * 60)
    print("4. xtemp.EMPLOYEE_F - check if exists and columns")
    print("=" * 60)
    try:
        cur.execute("""SELECT TOP 1 * FROM INFORMATION_SCHEMA.COLUMNS 
                      WHERE TABLE_NAME = 'EMPLOYEE_F' AND TABLE_SCHEMA = 'xtemp'""")
        row = cur.fetchone()
        if row:
            cur.execute("""SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH 
                          FROM INFORMATION_SCHEMA.COLUMNS 
                          WHERE TABLE_NAME = 'EMPLOYEE_F' AND TABLE_SCHEMA = 'xtemp'
                          ORDER BY ORDINAL_POSITION""")
            cols = cur.fetchall()
            for c in cols:
                print(f"  {c[0]} ({c[1]}, {c[2]})")
        else:
            print("  TABLE NOT FOUND in xtemp schema")
            # Try other schemas
            cur.execute("""SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
                          WHERE TABLE_NAME LIKE '%EMPLOYEE%' ORDER BY TABLE_SCHEMA, TABLE_NAME""")
            rows = cur.fetchall()
            print("  Employee-related tables found:")
            for r in rows:
                print(f"    {r[0]}.{r[1]}")
    except Exception as e:
        print(f"  Error: {e}")

    print()
    print("=" * 60)
    print("5. APP_ADMINS for APP_ID=22")
    print("=" * 60)
    cur.execute("SELECT * FROM dbo.APP_ADMINS WHERE APP_ID = 22")
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    print(f"  Columns: {cols}")
    for r in rows:
        print(f"  {dict(zip(cols, r))}")
