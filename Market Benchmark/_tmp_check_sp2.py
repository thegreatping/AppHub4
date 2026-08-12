import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# What got projected to 20260726?
rows = conn.execute("""
    SELECT PARENT_PROPERTY_KEY, COMP_PROPERTY_KEY, COMP_PROPERTY_NAME
    FROM dbo.COMP_ASSIGNMENTS WHERE DATE_KEY = 20260726
""").fetchall()
print(f"All 20260726 rows ({len(rows)}):")
for r in rows:
    print(f"  parent={r[0]}, comp_key={r[1]}, name={r[2]}")

# Check if there's a PARENT_COMP_KEY column issue
print("\n--- Column check ---")
cur = conn.execute("SELECT TOP 1 * FROM dbo.COMP_ASSIGNMENTS")
cols = [d[0] for d in cur.description]
print("Columns:", cols)

# The SP joins on PARENT_COMP_KEY — does that column exist?
if "PARENT_COMP_KEY" in cols:
    print("\nPARENT_COMP_KEY exists")
    # Check how many 0719 rows have a non-null PARENT_COMP_KEY
    r = conn.execute("SELECT COUNT(*), COUNT(PARENT_COMP_KEY) FROM dbo.COMP_ASSIGNMENTS WHERE DATE_KEY=20260719").fetchone()
    print(f"  0719: total={r[0]}, with PARENT_COMP_KEY={r[1]}")
else:
    print("\nPARENT_COMP_KEY does NOT exist — SP may reference wrong column!")
    print("Available columns with 'PARENT':", [c for c in cols if 'PARENT' in c.upper()])
