import sys; sys.path.insert(0,'.')
from dotenv import load_dotenv; load_dotenv()
from helpers import load_env, SafeConnection

conn = SafeConnection(load_env(), 'WH_STAGING', None, direct=True)

print("Executing AY_CUTOVER_ACTIONFLOW_SP @CONFIRM_ROLLOVER=1 ...")
conn.execute("EXEC [dbo].[AY_CUTOVER_ACTIONFLOW_SP] @CONFIRM_ROLLOVER = 1")
print("SP completed.")

print("\n--- AY_0 after rollover ---")
rows = conn.fetchall("SELECT AY_KEY, RELATIVE_AY FROM [dbo].[AY_0] ORDER BY AY_KEY")
for r in rows:
    print(f"  AY_KEY={r[0]}  RELATIVE_AY={r[1]}")

print("\n--- ACADEMIC_YEAR_0 after rollover ---")
rows2 = conn.fetchall("""
    SELECT AY_KEY, RELATIVE_AY, FLAG_AY_CURRENT_AY, FLAG_AY_PRELEASE_AY, FLAG_AY_PREVIOUS_AY
    FROM [dbo].[ACADEMIC_YEAR_0]
    ORDER BY AY_KEY
""")
for r in rows2:
    print(f"  AY_KEY={r[0]}  RELATIVE_AY={r[1]}  CURRENT={r[2]}  PRELEASE={r[3]}  PREVIOUS={r[4]}")

print("\n--- Backup tables created ---")
rows3 = conn.fetchall("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME LIKE '%_bak_2026%'
    ORDER BY TABLE_NAME
""")
for r in rows3:
    print(f"  {r[0]}")
