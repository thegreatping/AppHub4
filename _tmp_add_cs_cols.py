"""Add CS_REP and CS_MGR columns to dbo.PROPERTY_0."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Verify columns don't already exist
cur = conn.execute("""
    SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='PROPERTY_0'
      AND COLUMN_NAME IN ('CS_REP_NAME','CS_REP_EMAIL','CS_REP_EMP_CODE',
                          'CS_MGR_NAME','CS_MGR_EMAIL','CS_MGR_EMP_CODE')
""")
existing = [r[0] for r in cur.fetchall()]
if existing:
    print(f"Already exist (skipping): {existing}")

to_add = [c for c in ['CS_REP_NAME','CS_REP_EMAIL','CS_REP_EMP_CODE',
                       'CS_MGR_NAME','CS_MGR_EMAIL','CS_MGR_EMP_CODE']
          if c not in existing]

if not to_add:
    print("All columns already exist. Nothing to do.")
else:
    cols_sql = ",\n    ".join(
        f"[{c}] varchar({'50' if 'EMP_CODE' in c else '255'}) NULL"
        for c in to_add
    )
    sql = f"ALTER TABLE dbo.PROPERTY_0 ADD\n    {cols_sql}"
    print("Executing:\n" + sql)
    conn.execute(sql)
    print(f"\nOK — {len(to_add)} column(s) added: {to_add}")

    # Verify
    cur = conn.execute("""
        SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='PROPERTY_0'
          AND COLUMN_NAME LIKE 'CS_%'
        ORDER BY ORDINAL_POSITION
    """)
    print("\nVerification — CS columns in PROPERTY_0:")
    for r in cur.fetchall():
        print(f"  {r[0]:30s}  {r[1]}({r[2]})")
