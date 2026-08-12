"""Check Adaptive weekly tables and what properties have weekly leasing history."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Check Adaptive_Weekly_Tracker_Targets structure
print("=== Adaptive_Weekly_Tracker_Targets - sample rows ===")
cur = conn.execute("SELECT TOP 3 * FROM dbo.Adaptive_Weekly_Tracker_Targets")
cols = [d[0] for d in cur.description]
for r in cur.fetchall():
    print("  ", dict(zip(cols, r)))

# Check Adaptive_Z_WeeklyTracker
print("\n=== Adaptive_Z_WeeklyTracker columns ===")
cur = conn.execute("SELECT TOP 0 * FROM dbo.Adaptive_Z_WeeklyTracker")
print("  ", [d[0] for d in cur.description])
cur2 = conn.execute("SELECT TOP 3 * FROM dbo.Adaptive_Z_WeeklyTracker")
cols2 = [d[0] for d in cur2.description]
for r in cur2.fetchall():
    print("  ", dict(zip(cols2, r)))

# Check PROPDASH_FACT
print("\n=== PROPDASH_FACT columns ===")
cur = conn.execute("SELECT TOP 0 * FROM dbo.PROPDASH_FACT")
print("  ", [d[0] for d in cur.description])

# Check properties in L0_STATIC_HISTORY_BY_WEEK that are also in RFS
print("\n=== Properties in L0_STATIC_HISTORY_BY_WEEK matching RFS properties ===")
cur = conn.execute("""
    SELECT DISTINCT h.PROPERTY_KEY, h.PROPERTY_NAME, MAX(h.FOR_AY) as MAX_AY, COUNT(*) as ROW_COUNT
    FROM dbo.L0_STATIC_HISTORY_BY_WEEK h
    WHERE h.HIST_WEEKLY_NEW > 0 OR h.HIST_WEEKLY_RENEWAL > 0
    GROUP BY h.PROPERTY_KEY, h.PROPERTY_NAME
    ORDER BY h.PROPERTY_NAME
""")
rows = cur.fetchall()
print(f"  {len(rows)} properties with non-zero weekly data")
for r in rows[:10]:
    print(f"  {r[0]}: {r[1]} - max AY={r[2]}, rows={r[3]}")

# GeoCentral
print("\n=== L0_STATIC_HISTORY_BY_WEEK - GeoCentral (1069) ===")
cur = conn.execute("""
    SELECT FOR_AY, LEASING_WEEK_NBR, WEEK_START_DATE_MONDAY,
           HIST_WEEKLY_NEW, HIST_WEEKLY_RENEWAL
    FROM dbo.L0_STATIC_HISTORY_BY_WEEK
    WHERE PROPERTY_KEY=1069
    ORDER BY FOR_AY DESC, LEASING_WEEK_NBR
""")
rows2 = cur.fetchall()
print(f"  {len(rows2)} rows")
for r in rows2[:10]:
    print(f"  AY={r[0]} Wk{r[1]} ({r[2]}): New={r[3]} Ren={r[4]}")

conn.close()
