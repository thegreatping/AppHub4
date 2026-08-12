"""Sample L0_STATIC_HISTORY_BY_WEEK for weekly leasing velocity."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Check what properties have data
print("=== L0_STATIC_HISTORY_BY_WEEK - properties with data ===")
cur = conn.execute("SELECT DISTINCT PROPERTY_KEY, PROPERTY_NAME FROM dbo.L0_STATIC_HISTORY_BY_WEEK ORDER BY PROPERTY_NAME")
rows = cur.fetchall()
print(f"  {len(rows)} properties")
for r in rows[:10]:
    print(f"  {r[0]}: {r[1]}")

# Sample for a property that has data
if rows:
    pk = rows[0][0]
    print(f"\n=== Sample rows for property {pk} ===")
    cur = conn.execute("""
        SELECT TOP 15
            PROPERTY_KEY, FOR_AY, LEASING_WEEK_NBR, LEASING_WEEK_REVERSE_ID,
            WEEK_START_DATE_MONDAY, WEEK_END_DATE_SUNDAY,
            HIST_WEEKLY_NEW, HIST_WEEKLY_RENEWAL,
            HIST_CUM_NEW, HIST_CUM_RENEWAL
        FROM dbo.L0_STATIC_HISTORY_BY_WEEK
        WHERE PROPERTY_KEY=?
        ORDER BY FOR_AY DESC, LEASING_WEEK_NBR
    """, (pk,))
    cols = [d[0] for d in cur.description]
    for r in cur.fetchall():
        print("  ", dict(zip(cols, r)))

# Check the FLOORPLAN_ACTUALS_RENT more carefully
print("\n=== FLOORPLAN_ACTUALS_RENT - 48 WEST (9797) fp 26537 AY=2026 ===")
cur = conn.execute("""
    SELECT ROW_NUMBER, AY, LEASED_COUNT_NEW, LEASED_COUNT_RENEWAL, LEASED_COUNT_TOTAL,
           INTERVAL_TYPE_CONFORMED
    FROM dbo.FLOORPLAN_ACTUALS_RENT
    WHERE PROPERTY_KEY=9797 AND FLOORPLAN_KEY=26537 AND AY=2026
    ORDER BY ROW_NUMBER
""")
cols2 = [d[0] for d in cur.description]
for r in cur.fetchall():
    print("  ", dict(zip(cols2, r)))

# Also check FLOORPLAN_ACTUALS_RENT for AY=2025
print("\n=== FLOORPLAN_ACTUALS_RENT - 48 WEST (9797) fp 26537 AY=2025 ===")
cur = conn.execute("""
    SELECT TOP 15 ROW_NUMBER, AY, LEASED_COUNT_NEW, LEASED_COUNT_RENEWAL, LEASED_COUNT_TOTAL
    FROM dbo.FLOORPLAN_ACTUALS_RENT
    WHERE PROPERTY_KEY=9797 AND FLOORPLAN_KEY=26537 AND AY=2025
    ORDER BY ROW_NUMBER
""")
cols3 = [d[0] for d in cur.description]
for r in cur.fetchall():
    print("  ", dict(zip(cols3, r)))

# Also look at FORECAST_BUDGET_TIERS columns
print("\n=== FORECAST_BUDGET_TIERS columns ===")
cur = conn.execute("SELECT TOP 0 * FROM dbo.FORECAST_BUDGET_TIERS")
print("  ", [d[0] for d in cur.description])
cur2 = conn.execute("SELECT TOP 3 * FROM dbo.FORECAST_BUDGET_TIERS WHERE PROPERTY_KEY=9797 AND FLOORPLAN_KEY=26537 AND AY=2026")
cols4 = [d[0] for d in cur2.description]
for r in cur2.fetchall():
    print("  ", dict(zip(cols4, r)))

conn.close()
