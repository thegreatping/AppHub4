"""Check FASTTRACK_RECOMMENDATION data."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

print("=" * 60)
print("1. Total row count")
print("=" * 60)
cur = conn.execute("SELECT COUNT(*) FROM dbo.FASTTRACK_RECOMMENDATION")
print(f"  {cur.fetchone()[0]} rows")

print("\n" + "=" * 60)
print("2. DISTINCT RECOMMENDED_FASTTRACK values")
print("=" * 60)
cur = conn.execute("SELECT DISTINCT RECOMMENDED_FASTTRACK FROM dbo.FASTTRACK_RECOMMENDATION ORDER BY RECOMMENDED_FASTTRACK")
for r in cur.fetchall():
    print(f"  '{r[0]}'")

print("\n" + "=" * 60)
print("3. Sample rows (top 5)")
print("=" * 60)
cur = conn.execute("SELECT TOP 5 ID, EMPLOYEE_RECOMMENDED, CURRENT_POSITION, CURRENT_PROPERTY, RECOMMENDED_FASTTRACK, MODIFIED_BY, DATE_MODIFIED FROM dbo.FASTTRACK_RECOMMENDATION ORDER BY ID DESC")
for r in cur.fetchall():
    print(f"  ID={r[0]} | Emp={r[1]} | Pos={r[2]} | Prop={r[3]} | Track={r[4]} | By={r[5]} | Date={r[6]}")

print("\n" + "=" * 60)
print("4. APP_ADMINS for APP_ID=20")
print("=" * 60)
cur = conn.execute("SELECT ID, ADMIN_EMAIL, DATE_CREATED FROM dbo.APP_ADMINS WHERE APP_ID = 20 ORDER BY ID")
for r in cur.fetchall():
    print(f"  ID={r[0]} | Email={r[1]} | Date={r[2]}")
