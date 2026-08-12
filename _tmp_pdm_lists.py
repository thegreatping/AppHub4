"""Research LIST_ fields and dropdown values in PROPERTY_0."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import SafeConnection, load_env

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# List fields distinct values
for col in ['LIST_MANAGED', 'LIST_STATUS', 'LIST_TRANSITIONTYPE', 'LIST_TYPE',
            'PROPERTY_TYPE', 'MANAGEMENT_TYPE', 'LIFECYCLE_STATUS', 'LIFECYCLE_STEP',
            'TRANSITION_TYPE', 'CURRENT_PHASE', 'STATUS', 'SOURCE_SYSTEM']:
    cur = conn.execute(f"SELECT DISTINCT [{col}] FROM dbo.PROPERTY_0 WHERE [{col}] IS NOT NULL ORDER BY [{col}]")
    vals = [r[0] for r in cur.fetchall()]
    print(f"{col} ({len(vals)} values): {vals[:20]}")

# Check what MANAGEMENT_TYPE_KEY values map to
print("\n=== MANAGEMENT_TYPE_KEY ===")
cur = conn.execute("SELECT DISTINCT MANAGEMENT_TYPE_KEY, MANAGEMENT_TYPE FROM dbo.PROPERTY_0 WHERE MANAGEMENT_TYPE IS NOT NULL ORDER BY MANAGEMENT_TYPE_KEY")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

# Check PROPERTY_TYPE_KEY
print("\n=== PROPERTY_TYPE_KEY ===")
cur = conn.execute("SELECT DISTINCT PROPERTY_TYPE_KEY, PROPERTY_TYPE FROM dbo.PROPERTY_0 WHERE PROPERTY_TYPE IS NOT NULL ORDER BY PROPERTY_TYPE_KEY")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

# Check TRANSITION_TYPE_KEY
print("\n=== TRANSITION_TYPE_KEY ===")
cur = conn.execute("SELECT DISTINCT TRANSITION_TYPE_KEY, TRANSITION_TYPE FROM dbo.PROPERTY_0 WHERE TRANSITION_TYPE IS NOT NULL ORDER BY TRANSITION_TYPE_KEY")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

conn.close()
