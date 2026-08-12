"""Final check: PROPDASH_FACT and KPI_0 for actual weekly leasing data."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# PROPDASH_FACT
print("=== PROPDASH_FACT - distinct component names ===")
cur = conn.execute("SELECT DISTINCT COMPONENT_NAME FROM dbo.PROPDASH_FACT ORDER BY COMPONENT_NAME")
for r in cur.fetchall():
    print(f"  {r[0]}")

# Check what AY mapping Adaptive uses - 26-27 AY = AY 2027 or AY 2026?
# Based on context: leasing for Fall 2026 move-in = "26-27 AY" = what we call AY=2026
# So: AY 2026 → "26-27 AY", AY 2025 → "25-26 AY"

# Key question: Can I join Adaptive_Weekly_Tracker_Targets.Levels to PROPERTY_KEY?
# The Levels format is "{number} {PropertyName}"
print("\n=== Adaptive Levels -> PROPERTY_KEY mapping for 48 West / GeoCentral ===")
cur = conn.execute("""
    SELECT DISTINCT t.Levels
    FROM dbo.Adaptive_Weekly_Tracker_Targets t
    WHERE t.Levels LIKE '%48%West%' OR t.Levels LIKE '%GeoCentral%' OR t.Levels LIKE '%Geocentral%'
""")
for r in cur.fetchall():
    print(f"  Levels='{r[0]}'")

# Check if there's a lookup table mapping Levels/names to PROPERTY_KEY
print("\n=== PROPERTY_0 lookup for 48 West and GeoCentral ===")
cur = conn.execute("""
    SELECT PROPERTY_KEY, PROPERTY_NAME, PROPERTY_ID
    FROM dbo.PROPERTY_0
    WHERE PROPERTY_NAME LIKE '%48%WEST%' OR PROPERTY_NAME LIKE '%GEOCENTRAL%'
""")
for r in cur.fetchall():
    print(f"  KEY={r[0]}, NAME={r[1]}, ID={r[2]}")

# Adaptive_Weekly_Tracker_Targets - what is the week number format and range?
print("\n=== Adaptive_Weekly_Tracker_Targets - distinct weeks for 48 West AY 26-27 ===")
cur = conn.execute("""
    SELECT Week_Beginning,
           CAST(SUBSTRING(Week_Beginning, 2, 10) AS INT) as wk_num,
           Total_Weekly
    FROM dbo.Adaptive_Weekly_Tracker_Targets
    WHERE Levels = '102 48 West' AND Academic_Yr = '26-27 AY'
    ORDER BY CAST(SUBSTRING(Week_Beginning, 2, 10) AS INT)
""")
for r in cur.fetchall():
    print(f"  {r[0]} ({r[1]}): Total={r[2]}")

conn.close()
