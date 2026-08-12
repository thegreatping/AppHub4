"""Check MENTOR_CERTIFICATION data."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

print("=" * 60)
print("1. Total row count")
print("=" * 60)
cur = conn.execute("SELECT COUNT(*) FROM dbo.MENTOR_CERTIFICATION")
print(f"  {cur.fetchone()[0]} rows")

print("\n" + "=" * 60)
print("2. Sample rows (top 5)")
print("=" * 60)
cur = conn.execute("SELECT TOP 5 ID, MENTOR_NAME, CURRENT_POSITION, CURRENT_PROPERTY_NAME, SUBMITTED_BY, MODIFIED_DATETIME FROM dbo.MENTOR_CERTIFICATION ORDER BY ID DESC")
for r in cur.fetchall():
    print(f"  ID={r[0]} | Name={r[1]} | Pos={r[2]} | Prop={r[3]} | By={r[4]} | Date={r[5]}")

print("\n" + "=" * 60)
print("3. APP_ADMINS for APP_ID=21")
print("=" * 60)
cur = conn.execute("SELECT ID, ADMIN_EMAIL, DATE_CREATED FROM dbo.APP_ADMINS WHERE APP_ID = 21 ORDER BY ID")
for r in cur.fetchall():
    print(f"  ID={r[0]} | Email={r[1]} | Date={r[2]}")
