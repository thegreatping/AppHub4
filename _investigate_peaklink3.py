"""Investigate PeakLink - APP_LOCATION_LIST and Power App details."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

print("=" * 70)
print("1. APP_LOCATION_LIST TABLE")
print("=" * 70)
cols = conn.fetchall("""
    SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'APP_LOCATION_LIST'
    ORDER BY ORDINAL_POSITION
""")
print(f"\nColumns ({len(cols)}):")
for c in cols:
    print(f"  {c[0]:30s} {c[1]:15s} len={c[2]}")

count = conn.fetchall("SELECT COUNT(*) FROM dbo.APP_LOCATION_LIST")
print(f"\nTotal rows: {count[0][0]}")

sample = conn.fetchall("SELECT TOP 10 * FROM dbo.APP_LOCATION_LIST ORDER BY 1")
print("\nSample rows:")
for s in sample:
    print(f"  {s}")

print("\n" + "=" * 70)
print("2. CHECK SUGGESTION TYPES IN POWER APPS METADATA")
print("=" * 70)
# Check if there's an APP_CONFIG or APP_SETTINGS type table
config_tables = conn.fetchall("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME LIKE '%CONFIG%' OR TABLE_NAME LIKE '%SETTING%'
       OR TABLE_NAME LIKE '%APP_LIST%' OR TABLE_NAME LIKE '%APP_PARAM%'
    ORDER BY TABLE_NAME
""")
print(f"\nConfig/Settings tables ({len(config_tables)}):")
for t in config_tables:
    print(f"  {t[0]}")

print("\n" + "=" * 70)
print("3. APP_LIST FULL SCHEMA")
print("=" * 70)
app_cols = conn.fetchall("""
    SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'APP_LIST'
    ORDER BY ORDINAL_POSITION
""")
for c in app_cols:
    print(f"  {c[0]:30s} {c[1]:15s} len={c[2]}")

print("\n" + "=" * 70)
print("4. PEAKLINK TABLE - IDENTITY/SEQUENCE INFO")
print("=" * 70)
identity = conn.fetchall("""
    SELECT c.name, ic.seed_value, ic.increment_value, ic.last_value
    FROM sys.identity_columns ic
    JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
    WHERE ic.object_id = OBJECT_ID('dbo.PEAKLINK')
""")
if identity:
    for i in identity:
        print(f"  Column: {i[0]}, Seed: {i[1]}, Increment: {i[2]}, Last: {i[3]}")
else:
    print("  No identity column (ID must be manually generated)")

print("\n" + "=" * 70)
print("5. CHECK FOR POWER AUTOMATE / EMAIL TABLES")
print("=" * 70)
email_tables = conn.fetchall("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME LIKE '%EMAIL%' OR TABLE_NAME LIKE '%NOTIFICATION%'
       OR TABLE_NAME LIKE '%QUEUE%' OR TABLE_NAME LIKE '%ALERT%'
    ORDER BY TABLE_NAME
""")
print(f"\nEmail/Notification tables ({len(email_tables)}):")
for t in email_tables:
    print(f"  {t[0]}")

# Check FAS_PROPERTY_EMAIL_TARGETS
print("\n" + "=" * 70)
print("6. FAS_PROPERTY_EMAIL_TARGETS (might be relevant)")
print("=" * 70)
fas_cols = conn.fetchall("""
    SELECT COLUMN_NAME, DATA_TYPE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'FAS_PROPERTY_EMAIL_TARGETS'
    ORDER BY ORDINAL_POSITION
""")
print(f"\nColumns:")
for c in fas_cols:
    print(f"  {c[0]:30s} {c[1]}")
fas_sample = conn.fetchall("SELECT TOP 5 * FROM dbo.FAS_PROPERTY_EMAIL_TARGETS")
print(f"\nSample:")
for s in fas_sample:
    print(f"  {s}")

conn.close()
