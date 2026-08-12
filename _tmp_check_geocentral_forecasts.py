"""Check all GeoCentral forecasts across all AYs."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Search all AYs for GeoCentral (1069) including forecasts with "Melissa" or "July" in name
sql = """
    SELECT FORECAST_KEY, FORECAST_NAME, AY, FLAG_ARCHIVED, FLAG_APPROVED, DATE_CREATED
    FROM dbo.FORECAST_FORECASTS
    WHERE PROPERTY_KEY = 1069
    ORDER BY AY DESC, FLAG_ARCHIVED, FORECAST_NAME
"""
rows = conn.execute(sql).fetchall()
print(f"Total forecasts for GeoCentral: {len(rows)}")
for r in rows:
    print(f"  KEY={r[0]}, AY={r[2]}, ARCHIVED={r[3]}, NAME={r[1]}")

print()
# Search for Melissa across all properties
print("Searching for 'Melissa July' across ALL properties...")
sql2 = """
    SELECT FORECAST_KEY, FORECAST_NAME, AY, PROPERTY_KEY, PROPERTY_NAME, FLAG_ARCHIVED
    FROM dbo.FORECAST_FORECASTS
    WHERE FORECAST_NAME LIKE '%Melissa%July%' OR FORECAST_NAME LIKE '%July%22%'
    ORDER BY PROPERTY_NAME, AY DESC
"""
rows2 = conn.execute(sql2).fetchall()
print(f"Found {len(rows2)} matches:")
for r in rows2:
    print(f"  KEY={r[0]}, PROP={r[4]} ({r[3]}), AY={r[2]}, ARCHIVED={r[5]}, NAME={r[1]}")

conn.close()
